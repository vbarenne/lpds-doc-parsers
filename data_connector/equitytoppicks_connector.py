__author__ = ['Victoria Barenne']
__version__ = 'v2.0'


import os
from pdfminer.high_level import extract_pages
from pdfminer.layout import LTTextContainer, LTPage, LTTextBoxHorizontal, LTLine
from data_connector.base_connector import BaseConnector
from utils.pdf_helper.doc_helper import get_date_from_name, get_name_from_cover
from utils.pdf_helper.text_helper import is_header_match, remove_footer, get_char_colors, remove_hyphenation, concat_lines, remove_uncommon_utf8, clean_text, get_colors, get_jb_rating
import numpy as np
import pandas as pd
from utils.table_extractor import get_n_th_line_height
import re
from datetime import datetime

class EquityTopPicksConnector(BaseConnector):
    doc_type = 'Equity Top Picks'
    contact_page = 'Contact \n'
    left_sec_x0 = 250
    page_start = 2
    
    @classmethod
    def get_all_components(cls, fp):
        pages = list(extract_pages(fp))

        pub_date = cls.get_pub_date(pages[0])
        src_doc = os.path.basename(fp).replace('.pdf', '')
        stop_headers = ["MORNINGSTAR ANNEX", "IMPORTANT LEGAL INFORMATION", "IMPORTANT DISTRIBUTION INFORMATION"]

        equity_pages_no, deletion_pages_no = [], []
        equity_pages, deletion_pages = {}, []
        is_last_page = False

        for page_nbr, page in enumerate(pages):
            elements = [el for el in page]
            y0s = [el.y0 for el in page]
            header = elements[np.argmax(y0s)]
            if isinstance(header, LTTextBoxHorizontal):
                if not is_last_page:
                    is_last_page = header.get_text().startswith(tuple(stop_headers))
                if not header.get_text().startswith("EQUITY TOP PICKS") and not is_last_page:
                    equity_pages[clean_text(header.get_text())] = page
                    equity_pages_no.append(page_nbr + 1)
                elif header.get_text().startswith("EQUITY TOP PICKS - DELETIONS") and not is_last_page:
                    deletion_pages.append(page)
                    deletion_pages_no.append(page_nbr + 1)

        equity_extractions = []
        for equity, page in equity_pages.items():
            table_elements, text_elements, title = cls.equity_page_elements(page)
            investment_thesis, company_profile = cls.get_equity_sections(text_elements)
            key_info = cls.get_key_info_table(table_elements, equity)
            equity_extractions.append([title, key_info, investment_thesis, company_profile])
        
        metadata = cls.format_metadata(pub_date, src_doc, "Equity Top Picks", cls.doc_type)
        deletions_table = cls.get_deletions(deletion_pages)
        return equity_extractions, deletions_table, metadata, equity_pages_no, deletion_pages_no
    
    @classmethod
    def get_equity_sections(cls, elements, **kwargs):
        section_text = " ".join([el.get_text() for el in elements])
        company_profile = clean_text(section_text.split("Company Description")[1].split("Investment Rationale")[0])
        investment_thesis = clean_text(section_text.split("Investment Rationale")[-1])
        if investment_thesis[0]=="#":
            investment_thesis= investment_thesis[1:]                               
        return investment_thesis, company_profile

    @classmethod
    def equity_page_elements(cls, page):
        STOP_ELEMENTS = ["Julius Baer and should not be read", "^Calculation of total return", "Please find important legal", "# The Investment Rationale is provided by Julius Baer"]
        first_line_y0 = get_n_th_line_height(page, -1)
        max_y0 = max([el.y0 for el in page if isinstance(el, LTTextBoxHorizontal)])
        title = [el for el in page if el.y0>first_line_y0 and el.y0 <max_y0 and isinstance(el, LTTextBoxHorizontal)][0].get_text()
        end_table_y0 = [el.y0 for el in page if isinstance(el, LTTextBoxHorizontal) and el.get_text().startswith("Company Description")][0]
        table_elements, text_elements = [], []
        is_stop_element = False

        for element in page:
            if not is_stop_element:
                is_stop_element = element.get_text().startswith(tuple(STOP_ELEMENTS))
            if element.y0>end_table_y0 and element.y0<=first_line_y0:
                table_elements.append(element)
            elif element.y0<=end_table_y0 and element.x0 < 250 and isinstance(element, LTTextBoxHorizontal) and not is_stop_element:
                text_elements.append(element)

        return table_elements, text_elements, clean_text(title)

    @classmethod
    def get_key_info_table(cls, elements, name):
        key_info = []
        for el in elements:
            if isinstance(el, LTTextBoxHorizontal):
                key_info.append([el.x0, el.y0, el.get_text()])
        key_info = pd.DataFrame(data = key_info, columns = ["x0", "y0", "text"])

        y1, y2, y3 = get_n_th_line_height(elements, -1), get_n_th_line_height(elements, -2), get_n_th_line_height(elements, -3)
        equity, country = key_info[(key_info.y0<y1)&(key_info.y0>y2)].sort_values(by = ["x0"])["text"].values
        row = key_info[(key_info.y0<y2)&(key_info.y0>y3)].sort_values(by = "x0")
        sector = row.iloc[0]["text"]
        risk_rating = row.iloc[-1]["text"].split(":")[-1]
        rating = get_jb_rating(" ".join(row.text.values))
        infos = {"equity": equity, 
                "country": clean_text(country), 
                "sector": clean_text(sector), 
                "risk_rating": clean_text(risk_rating), 
                "rating": rating}

        for info in ["ISIN", "Bloomberg Ticker", "Currency"]:
            x0, y0, text = key_info[key_info.text.str.startswith(info)].values.flatten()
            value = key_info[(key_info.y0 == y0)&(key_info.x0>x0)].sort_values(by = "x0").iloc[0]["text"]
            infos[info] = clean_text(value)
        return infos

    @classmethod
    def get_deletions(cls, deletion_pages):
        all_deletions = []
        region = "Unknown"
        for page in deletion_pages: 
            deletions_table = []
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
            all_deletions.append(deletions_table)
        return all_deletions


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

    @classmethod
    def get_pub_date(cls, first_page):
        for el in first_page:
            if isinstance(el, LTTextBoxHorizontal) and bool(re.search(r'\d', el.get_text())): 
                date_str = el.get_text().split(",")[1].strip()
                date_str = datetime.strptime(date_str, '%d %B %Y')
                date_str = date_str.strftime("%Y-%m-%d") 
                return date_str