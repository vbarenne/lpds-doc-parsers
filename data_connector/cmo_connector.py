__author__ = ['Victoria Barenne']
__version__ = 'v2.0'

import os
from pdfminer.high_level import extract_pages
from pdfminer.layout import LTTextContainer, LTPage, LTTextBoxHorizontal, LTLine, LTChar
from data_connector.base_connector import BaseConnector
from utils.pdf_helper.doc_helper import get_date_from_header, get_name_from_cover, remove_legal_disclaimer, get_page_number, get_page_number_from_title, get_date_from_name
from utils.pdf_helper.text_helper import clean_text, is_text_in_font_size, concat_lines, get_colors, get_char_colors
from settings import JB_LEGAL_DISCLAIMER
import numpy as np
from datetime import datetime
from utils.table_extractor import table_extractor, get_n_th_line_height 
import pandas as pd

class CMOConnector(BaseConnector):
    doc_type = 'CMO Equity'
    left_sec_x0 = 300
    sec_title_font = 12

    @classmethod
    def get_json_all(cls, fp):
        pages = list(extract_pages(fp))
        json_list = []

        left_elements = cls.get_left_elements(pages[0])
        left_sections = cls.get_sections(left_elements, 11)

        title = left_sections[0][0]
        subtitle = left_sections[1][0]
        market_opportunity, company_profile, key_risks = "", "", ""
        src_doc = os.path.basename(fp).replace('.pdf', '')
        pub_date = cls.get_pub_date(pages[0])
        equity_name = title

        for sec in left_sections[2:]: 
            if sec[0].upper().startswith("MARKET OPPORTUNITY"):
                market_opportunity = sec[1]
        
        left_elements = cls.get_left_elements(pages[1])
        left_sections = cls.get_sections(left_elements, 8.9, reverse= True)
        for sec in left_sections: 
            if sec[0].upper().startswith("COMPANY PROFILE"):
                company_profile = sec[1]
            elif sec[0].upper().startswith("KEY RISKS"):
                key_risks = sec[1]

        key_information = cls.get_key_information(pages) 

        equity_json = {
                    "equity": equity_name,
                    "industries": [key_information.loc["sector"].item(), key_information.loc["subsector"].item()],
                    "country": key_information.loc["country"].item(),
                    "rating": key_information.loc["julius baer research rating"].item(),
                    "risk_rating": None,
                    "isin": key_information.loc["isin"].item(),
                    "bbg_ticker": None, 
                    "currency": key_information.loc["currency"].item().upper(), 
                    "investment_thesis": market_opportunity + key_risks,
                    "company_profile": company_profile,
                    "strengths": None,
                    "weaknesses": None,
                    "opportunities": None,
                    "threats": None,
                    "additional_information": None,
                    "source_document": src_doc,
                    "document_name": title + " " + subtitle,
                    "publication_date": pub_date,
                    "document_type": cls.doc_type
                    }

        return equity_json


    @classmethod
    def get_left_elements(cls, page):
        left_elements = []
        first_line_y0 = max([el.y0 for el in page if isinstance(el, LTLine)])
        is_chart, is_note_source = False, False

        for element in list(page):
            if not isinstance(element, LTTextBoxHorizontal):
                continue

            if not is_chart: 
                is_chart = element.get_text().upper().startswith("5-YEAR PERFORMANCE") or element.get_text().upper().startswith("FIVE-YEAR PERFORMANCE")

            if not is_note_source :
                is_note_source = element.get_text().startswith("Source:") or element.get_text().startswith("Note:")

            if element.y0 < first_line_y0 and element.y0 >= 50 and element.x0 < cls.left_sec_x0 and not is_chart and not is_note_source:
                left_elements.append(element)
                
        return left_elements

    @classmethod
    def get_key_information(cls, pages):
        page = pages[1]
        elements = pd.DataFrame(data = [[el.x0, el.y0, el.get_text().lower()] for el in page if isinstance(el, LTTextBoxHorizontal)],
                                columns = ["x0", "y0", "text"])
        key_info_y = elements[elements["text"].str.startswith("key information")]["y0"].item()
        ymax = max([el.y0 for el in page if (isinstance(el, LTLine) and el.x0 >cls.left_sec_x0 and el.y0 < key_info_y)])
        ymin = get_n_th_line_height(page, 0)
        key_information = table_extractor(page, ymin, ymax, xmin = cls.left_sec_x0, row_lines = True, has_header = False)
        return key_information

    @classmethod
    def get_sections(cls, elements, font_lower_tsh, reverse = False, **kwargs):
        sections = []
        current_header = ""
        curr_sec = []
        for i, element in enumerate(elements):
            header, txt = cls.get_header_text(element, font_lower_tsh, reverse)
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
    def get_header_text(cls, element: LTTextBoxHorizontal, font_lower_tsh, reverse = False):
            header_list = []
            text_list = []
            content = element.get_text()
            font_size = max([char.size for text_line in element for char in text_line if isinstance(char, LTChar)])
            for word in content.split(" "):
                cond = (font_size<font_lower_tsh) if reverse else (font_size>=font_lower_tsh)
                if cond:
                    header_list.append(word)
                else: 
                    text_list.append(word)

            header = concat_lines(' '.join(header_list))
            text = clean_text(' '.join(text_list))
            return header, text
    
    @classmethod
    def get_rating(cls, src_doc):
        if "Buy" in src_doc:
            return "Buy"
        if "Hold" in src_doc:
            return "Hold"
        if "Sell" in src_doc:
            return "Sell"
        else:
            return "Unknown"   

    @classmethod
    def get_pub_date(cls, first_page):
        first_line_y0 = max([el.y0 for el in first_page if isinstance(el, LTLine)])
        header_elements_x0 = [el.x0 for el in first_page if el.y0 > first_line_y0]
        date = [el for el in first_page if (el.y0 > first_line_y0 and el.x0 == max(header_elements_x0))][0].get_text()

        date_str = date.split(",")[0]
        date_str = datetime.strptime(date_str, '%d %B %Y')
        date_str = date_str.strftime("%Y-%m-%d")
        return date_str

