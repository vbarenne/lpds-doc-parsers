__author__ = ['Victoria Barenne']
__version__ = 'v2.0'

import os
from pdfminer.high_level import extract_pages
from pdfminer.layout import LTTextContainer, LTPage, LTTextBoxHorizontal
from data_connector.base_connector import BaseConnector
from utils.pdf_helper.doc_helper import get_date_from_header, get_name_from_cover, remove_legal_disclaimer, get_page_number, get_page_number_from_title, get_date_from_name
from utils.pdf_helper.text_helper import clean_text, is_text_in_font_size, concat_lines, get_colors, get_char_colors
from settings import JB_LEGAL_DISCLAIMER
import numpy as np

class EquityDeepDiveConnector(BaseConnector):
    doc_type = 'Equity Deep Dive'
    left_sec_x0 = 250
    sec_title_font = 12

    @classmethod
    def get_json_all(cls, fp):
        pages = list(extract_pages(fp))
        json_list = []

        src_doc = os.path.basename(fp).replace('.pdf', '')
        front_page_elements = [el for el in pages[0]]
        equity_name = clean_text(front_page_elements[0].get_text())
        equity_info = front_page_elements[1].get_text().split("|")
        doc_name = clean_text(front_page_elements[3].get_text())
        industries = equity_info[0].strip().title().split("/")
        country = equity_info[1].strip().title()
        pub_date = equity_info[2][:11]
        rating = cls.get_rating(src_doc)

        investment_thesis, company_profile, free_text = cls.get_first_page(pages[0])
        strengths, weaknesses, opportunities, threats = cls.get_swot_analysis(pages[1])

        equity_json = {
                    "equity": equity_name,
                    "industries": industries,
                    "country": country,
                    "rating": rating,
                    "risk_rating": None,
                    "isin": None,
                    "bbg_ticker": None, 
                    "currency": None, 
                    "investment_thesis": investment_thesis,
                    "company_profile": company_profile,
                    "strengths": strengths,
                    "weaknesses": weaknesses,
                    "opportunities": opportunities,
                    "threats": threats,
                    "additional_information": free_text,
                    "source_document": src_doc,
                    "document_name": doc_name,
                    "publication_date": pub_date,
                    "document_type": cls.doc_type
                    }

        return equity_json


    @classmethod
    def get_first_page(cls, page):
        left_elements, right_elements = [], []
        is_investment_thesis = False

        for element in list(page)[0:]:
            if not isinstance(element, LTTextBoxHorizontal):
                continue

            if not is_investment_thesis:
                is_investment_thesis = element.get_text().startswith("Investment thesis")
            
            if element.y0 >=50 and is_investment_thesis: 
                if element.x0 < cls.left_sec_x0:
                    left_elements.append(element)
                elif element.x0 >= cls.left_sec_x0:
                    right_elements.append(element)

        elements = left_elements + right_elements
        elements_cutoff = np.where([el.get_text().startswith("Performance") for el in elements])[0].min()
        elements = elements[:elements_cutoff]

        sections = cls.get_sections(elements)
        investment_thesis, company_profile = "unknown", "unknown"
        free_text = []
        for sec in sections: 
            if sec[0].startswith("Investment thesis"):
                investment_thesis = clean_text(sec[1])
            elif sec[0].startswith("Company profile"):
                company_profile = clean_text(sec[1])
            else: 
                free_text.append(sec[0] + sec[1])
        free_text = "".join(free_text)
        return investment_thesis, company_profile, free_text

    @classmethod
    def get_swot_analysis(cls, page):
        elements = [el.get_text() for el in list(page) if (isinstance(el, LTTextBoxHorizontal) and el.y0>=50 and el.x0<=cls.left_sec_x0)]
        swot = "".join(elements)
        sections = []
        section_names = ['Strengths \n', "Weaknesses \n", "Opportunities \n", "Threats \n", "FACTS & FIGURES"]
        for i in range(4):
            sections.append(clean_text(swot.split(section_names[i])[1].split(section_names[i+1])[0]))
        return sections


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
    def get_rating(cls, src_doc):
        if "Buy" in src_doc:
            return "Buy"
        if "Hold" in src_doc:
            return "Hold"
        if "Sell" in src_doc:
            return "Sell"
        else:
            return "Unknown"   