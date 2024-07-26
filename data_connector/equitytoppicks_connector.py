__author__ = ['Victoria Barenne']
__version__ = 'v2.0'


import os
from pdfminer.high_level import extract_pages
from pdfminer.layout import LTTextContainer, LTPage, LTTextBoxHorizontal, LTLine
from data_connector.base_connector import BaseConnector
from utils.pdf_helper.doc_helper import get_date_from_name, get_name_from_cover
from utils.pdf_helper.text_helper import is_header_match, remove_footer, get_char_colors, remove_hyphenation, concat_lines, remove_uncommon_utf8, clean_text, get_colors
import numpy as np
import pandas as pd

class EquityTopPicksConnector(BaseConnector):
    doc_type = 'Equity Top Picks'
    contact_page = 'Contact \n'
    left_sec_x0 = 250
    page_start = 2
    
    @classmethod
    def get_json_all(cls, fp):
        pages = list(extract_pages(fp))
        json_list = []

        pub_date = get_date_from_name(os.path.basename(fp), cls.doc_type).replace("(","").replace(")","")
        src_doc = os.path.basename(fp).replace('.pdf', '')
        stop_headers = ["MORNINGSTAR ANNEX", "IMPORTANT LEGAL INFORMATION", "IMPORTANT DISTRIBUTION INFORMATION"]

        equity_pages = {}
        deletion_pages = []
        is_last_page = False
        for i, page in enumerate(pages):
            elements = [el for el in page]
            y0s = [el.y0 for el in page]
            header = elements[np.argmax(y0s)]
            if isinstance(header, LTTextBoxHorizontal):
                if not is_last_page:
                    is_last_page = header.get_text().startswith(tuple(stop_headers))
                if not header.get_text().startswith("EQUITY TOP PICKS") and not is_last_page:
                    equity_pages[clean_text(header.get_text())] = page
                elif header.get_text().startswith("EQUITY TOP PICKS - DELETIONS") and not is_last_page:
                    deletion_pages.append(page)

        for equity, page in equity_pages.items():
            table_elements, text_elements, title = cls.equity_page_elements(page)
            sections = cls.get_sections(text_elements)
            for sec in sections:
                if sec[0].startswith("Company Description"):
                    company_profile = clean_text(sec[1])
                elif sec[0].startswith('Investment Rationale'):
                    investment_thesis = clean_text(sec[1])
            key_info = cls.get_key_info_table(table_elements, equity)
            equity_json = {
                    "equity": equity,
                    "industries": [key_info["Sector"]],
                    "country": key_info["Country"],
                    "rating": key_info["rating"],
                    "risk_rating": key_info["risk_rating"],
                    "isin": key_info["ISIN"],
                    "bbg_ticker": key_info["Bloomberg Ticker"], 
                    "currency": key_info["Currency"], 
                    "investment_thesis": investment_thesis,
                    "company_profile": company_profile,
                    "strengths": None,
                    "weaknesses": None,
                    "opportunities": None,
                    "threats": None,
                    "additional_information": None,
                    "source_document": src_doc,
                    "document_name": title,
                    "publication_date": pub_date,
                    "document_type": cls.doc_type
                    }
            json_list.append(equity_json)
        
        deletions_table = cls.get_deletions(deletion_pages)

        return json_list, deletions_table
    
    @classmethod
    def get_sections(cls, elements, **kwargs):
        sections = []
        current_header = ""

        for i, element in enumerate(elements):
            header, txt = cls.get_header_text(element)
            if header!="":
                if current_header !="":
                    sections.append([current_header, "".join(curr_sec)])
                current_header = header
                curr_sec = [txt]
            else:
                curr_sec.append(txt)
        if len(curr_sec)>0:
            sections.append([current_header, "".join(curr_sec)])

        return sections

    @classmethod
    def equity_page_elements(cls, page):
        STOP_ELEMENTS = ["Julius Baer and should not be read", "^Calculation of total return", "Please find important legal", "# The Investment Rationale is provided by Julius Baer"]
        first_line_y0 = max([el.y0 for el in page if isinstance(el, LTLine)])
        max_y0 = max([el.y0 for el in page if isinstance(el, LTTextBoxHorizontal)])
        title = [el for el in page if el.y0>first_line_y0 and el.y0 <max_y0][0].get_text()
        end_table_y0 = [el.y0 for el in page if isinstance(el, LTTextBoxHorizontal) and el.get_text().startswith("Company Description")][0]
        table_elements, text_elements = [], []
        is_stop_element = False

        for element in page:
            if not is_stop_element:
                is_stop_element = element.get_text().startswith(tuple(STOP_ELEMENTS))
            if element.y0>end_table_y0 and element.y0<first_line_y0:
                table_elements.append(element)
            elif element.y0<=end_table_y0 and element.x0 < cls.left_sec_x0 and not is_stop_element and not element.get_text().startswith("#\n"):
                text_elements.append(element)
        
        return table_elements, text_elements, clean_text(title)

    @classmethod
    def get_key_info_table(cls, elements, name):
        key_info = []
        for el in elements:
            if isinstance(el, LTTextBoxHorizontal):
                key_info.append([el.x0, el.y0, el.get_text()])
        key_info = pd.DataFrame(data = key_info, columns = ["x0", "y0", "text"])

        x0, y0 = key_info[key_info.text.str.lower().str.strip()==name.lower().strip()][["x0", "y0"]].values.flatten()
        equity, country = key_info[(key_info.y0==y0)]["text"].values.flatten()
        x1, y1, sector = key_info[(key_info.x0==x0)&(key_info.y0<y0)].sort_values(by= "y0", ascending = False).iloc[0]
        risk_rating = key_info[(key_info.y0==y1)].sort_values(by= "x0").iloc[-1]["text"].split(":")[-1]
        infos = {"Country": clean_text(country), "Sector": clean_text(sector), "risk_rating": clean_text(risk_rating)}

        for info in ["ISIN", "Bloomberg Ticker", "Currency"]:
            x0, y0, text = key_info[key_info.text.str.startswith(info)].values.flatten()
            value = key_info[(key_info.y0 == y0)&(key_info.x0>x0)].sort_values(by = "x0").iloc[0]["text"]
            infos[info] = clean_text(value)
        rating = [clean_text(txt).capitalize().strip() for txt in key_info.text if clean_text(txt).lower().strip() in ["buy", "hold", "sell"]]
        infos["rating"] = rating[0] if len(rating)>0 else None

        return infos

    @classmethod
    def get_deletions(cls, deletion_pages):
        deletions_table = []
        region = "Unknown"
        for page in deletion_pages: 
            lines = [el.y0 for el in page if isinstance(el, LTLine)]
            first_line_y0, before_last_y0 =np.partition(lines, -2)[-2], np.partition(lines, 1)[1]
            elements = [el for el in page if (el.y0 >before_last_y0 and el.y0<first_line_y0 and isinstance(el, LTTextBoxHorizontal))]
            for y0 in -np.sort(-np.unique([el.y0 for el in elements])):
                row = [clean_text(el.get_text()) for el in elements if el.y0==y0]
                if len(row)==5:
                    deletions_table.append(row + region)
                elif len(row)==1:
                    region = row

        deletions_table = pd.DataFrame(data = deletions_table, 
                                    columns = ["Equity", "Date Added", "Date Removed", 
                                                "Total Return since Addition", "Reason for Deletion",
                                                "Region"])
        return deletions_table


    @classmethod
    def get_header_text(cls, element: LTTextBoxHorizontal):
            header_list = []
            text_list = []
            for i in range(1, len(element)+1):
                if 0 not in get_colors(list(element)[0:i]):
                    header_list.append(list(element)[i-1].get_text())
                else:
                    text_list.append(list(element)[i-1].get_text())

            header = concat_lines(''.join(header_list))
            text = clean_text(text_list)
            return header, text
