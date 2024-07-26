__author__ = ['Victoria Barenne']
__version__ = 'v2.0'

import os
from pdfminer.high_level import extract_pages
from pdfminer.layout import LTTextContainer, LTPage, LTTextBoxHorizontal, LTLine
from data_connector.base_connector import BaseConnector
from utils.pdf_helper.doc_helper import get_date_from_header, get_name_from_cover, remove_legal_disclaimer, get_page_number, get_page_number_from_title, get_date_from_name
from utils.pdf_helper.text_helper import clean_text, is_text_in_font_size, concat_lines, get_colors, get_char_colors
from settings import JB_LEGAL_DISCLAIMER
import numpy as np
import pandas as pd
from datetime import datetime
from fuzzywuzzy import fuzz
from utils.table_extractor import table_extractor, get_n_th_line_height

class EquitySwitchConnector(BaseConnector):
    doc_type = 'Equity Switch Idea'
    left_sec_x0 = 250
    sec_title_font = 12

    @classmethod
    def get_all_components(cls, fp):
        pages = list(extract_pages(fp))
        json_list = []

        src_doc = os.path.basename(fp).replace('.pdf', '')
        pub_date, doc_name, equity1_shortname, equity2_shortname, rating1, rating2 = cls.get_title_page_info(pages)

        comparaison_table = cls.extract_comparaison_table(pages[1], equity2_shortname)
        equity_json1, equity_json2 = cls.get_equity_json(comparaison_table)

        first_page_sec = cls.get_page_elements(pages[0])
        first_page_sec = cls.get_sections(first_page_sec)
        whats_the_story= first_page_sec[0][1]
        texta, headera =  first_page_sec[1][1], first_page_sec[1][0]
        textb, headerb =  first_page_sec[2][1], first_page_sec[2][0]

        metadata = cls.format_metadata(pub_date, src_doc, doc_name, cls.doc_type)
        return equity_json1, equity_json2, metadata, whats_the_story, headera, texta, headerb, textb, comparaison_table
    
    @classmethod
    def get_page_elements(cls, page):
        left_elements, right_elements = [], []
        is_whats_the_story = False

        for element in list(page):
            if not isinstance(element, LTTextBoxHorizontal):
                continue

            element_txt = element.get_text()
            if not is_whats_the_story:
                is_whats_the_story = element_txt.lower().startswith("what’s the story?")
            is_note_source = element.get_text().startswith("Source:") or element.get_text().startswith("Note:")
            is_chart = element.get_text().startswith("5-YEAR PERFORMANCE COMPARISON")

            if element.y0 >=50 and is_whats_the_story and not is_note_source and not is_chart: 
                if element.x0 < cls.left_sec_x0:
                    left_elements.append(element)
                elif element.x0 >= cls.left_sec_x0:
                    right_elements.append(element)

        elements = left_elements + right_elements
        return elements

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
                if (0, 0, 0, 1) not in get_colors(list(element)[0:i]):
                    header_list.append(list(element)[i-1].get_text())
                else:
                    text_list.append(list(element)[i-1].get_text())

            header = concat_lines(''.join(header_list))
            text = clean_text(text_list)
            return header, text
    
    @classmethod
    def extract_comparaison_table(cls, page, equity2_shortname):
        ymax = [el.y0 for el in page if isinstance(el, LTTextBoxHorizontal) and el.get_text().startswith("COMPARISON")][0]
        ymin = get_n_th_line_height(page, 0)
        lines = np.unique([el.y0 for el in page if isinstance(el, LTLine) and el.y0 < ymax])
        ymax, yother = np.partition(lines, -2)[-2], np.partition(lines, -1)[-1]

        comparaison_table = table_extractor(page, ymin, ymax, has_header = False)  
        equity_names = [clean_text(el.get_text()) for el in page if isinstance(el, LTTextBoxHorizontal) and el.y0 >ymax and el.y0 < yother and el.x0 <250]
        equity2 = "VISA"
        if len(equity_names)<2:
            equity1 = equity_names[0].lower().split(equity2_shortname.lower())[0]
            equity2 = equity_names[0].lower().split(equity1)[1]
            equity_names = [equity1.capitalize(), equity2.capitalize()]
        comparaison_table.loc["Equity"] = equity_names
        comparaison_table.columns = ["Equity1", "Equity2"]

        return comparaison_table
        

    @classmethod
    def get_title_page_info(cls, pages):
        first_line_y0 = max([el.y0 for el in pages[1] if isinstance(el, LTLine)])
        date_str = [el.get_text() for el in pages[1] if (el.y0>first_line_y0 and el.x0 >250 and isinstance(el, LTTextBoxHorizontal))][0]
        date_str = date_str.split(",")[0]
        date_str = datetime.strptime(date_str, '%d %B %Y')
        date_str = date_str.strftime("%Y-%m-%d")

        title = [el.get_text() for el in pages[0] if (isinstance(el, LTTextBoxHorizontal) and "BUY" in el.get_text() and "SELL" in el.get_text())][0]
        equity1, equity2 = title.split(",")
        rating1, rating2 = cls.get_rating(equity1), cls.get_rating(equity2)
        equity1, equity2 = "".join(equity1.strip().split(" ")[1:]), "".join(equity2.strip().split(" ")[1:])
        return date_str, clean_text(title), equity1, equity2, rating1, rating2
    
    @classmethod
    def get_rating(cls, txt):
        if "buy" in txt.lower():
            return "Buy"
        if "hold" in txt.lower():
            return "Hold"
        if "sell" in txt.lower():
            return "Sell"
        else:
            return "Unknown"   

    @classmethod
    def get_equity_json(cls, comparaison_table):
        json_list = []
        for equity_nbr in ["Equity1", "Equity2"]:
            equity, isin, country, sector, subsector, ccy, risk_rating, rating, ticker = comparaison_table.loc[["Equity", "ISIN", "Country", "Sector", "Sub-sector", "Ccy", "JB product risk rating", "JB Research / MS rating", "BBG Ticker"]][equity_nbr].values
            equity_json = cls.format_equity_info(equity, [sector] + [subsector], country, rating, risk_rating, isin, ticker, ccy.upper())
            json_list.append(equity_json)             
        return json_list