__author__ = ['Victoria Barenne']
__version__ = 'v2.0'


import os
from pdfminer.high_level import extract_pages
from pdfminer.layout import LTTextContainer, LTPage, LTTextBoxHorizontal, LTRect
from data_connector.base_connector import BaseConnector
from utils.pdf_helper.doc_helper import get_date_from_name, get_name_from_cover
from utils.pdf_helper.text_helper import is_header_match, remove_footer, get_char_colors, remove_hyphenation, concat_lines, remove_uncommon_utf8, clean_text, is_within_rectangles, get_colors
import numpy as np
from datetime import datetime 

class CIOMonthlyConnector(BaseConnector):
    doc_type = 'CIO Monthly'
    asset_allocation = 'Current asset allocation\n'
    first_page = "FIRST PAGE"
    left_sec_x0 = 250
    page_start = 1
    
    @classmethod
    def get_json_all(cls, fp):
        pages = list(extract_pages(fp))
        json_list = []
        page_num = 1
        is_sec_element = True

        doc_name, pub_date = [el.get_text().strip() for el in pages[2] if isinstance(el, LTTextBoxHorizontal)][:2]
        pub_date = datetime.strptime(pub_date, '%d %B %Y').strftime('%Y-%m-%d')
        src_doc = os.path.basename(fp).replace('.pdf', '')
        first_page_sec = cls.get_first_page(page = pages[0])
        sec_json = cls.format_section(pub_date=pub_date, src_doc=src_doc, pg_num=page_num,
                                      doc_name=doc_name, sec_title=cls.first_page, sec_header='',
                                      sec_text=first_page_sec, series=cls.doc_type)
        json_list.append(sec_json)

        cur_header = ""
        cur_section = []
        for page in pages[1:]:
            elements, is_last_page, is_sec_element = cls.get_page_elements(page, is_sec_element)
            sections, cur_header, cur_section = cls.get_sections(elements, cur_header=cur_header, cur_section=cur_section)
            page_num += 1
            for sec_header, sec_text in sections:
                sec_json = cls.format_section(pub_date=pub_date, src_doc="CIO Monthly {}".format(pub_date), pg_num=page_num, doc_name=doc_name, sec_title=doc_name, sec_header=sec_header, sec_text=sec_text, series="CIO Weekly")
                json_list.append(sec_json)

            if is_last_page:
                break
        
        if len(cur_section) > 0:
            sec_text = clean_text(cur_section)
            sec_json = cls.format_section(pub_date=pub_date, src_doc="CIO Monthly {}".format(pub_date), pg_num=page_num, doc_name=doc_name, sec_title=doc_name, sec_header=cur_header, sec_text=sec_text, series="CIO Weekly")
            json_list.append(sec_json)


        json_list = cls.join_sections(json_list)

        return json_list
    
    @classmethod
    def get_first_page(cls, page: LTPage):
        first_page_sec = []
        elements, _, _ = cls.get_page_elements(page, True)
        rects = [el for el in page if isinstance(el, LTRect)]
        filtered_elements = [is_within_rectangles(el, rects) for el in elements]
        box_end = np.where(filtered_elements)[0].max()
        for element in elements[box_end+1:]:
                if get_colors(element) == {(0, 0, 0)}:
                    first_page_sec.append(element.get_text())
        sec_text = clean_text(first_page_sec)
        # sec_text = remove_legal_disclaimer(sec_text, JB_LEGAL_DISCLAIMER)
        return sec_text
    
    @classmethod
    def get_page_elements(cls, page, is_sec_element):
        left_elements, right_elements = [], []
        is_last_page = False
        is_contact_box = False

        for element in list(page)[cls.page_start:]:
            if isinstance(element, LTTextContainer) and cls.asset_allocation in element.get_text():
                is_last_page = True
                if element.x0 < cls.left_sec_x0:
                    break
            
            if not isinstance(element, LTTextBoxHorizontal):
                continue

            if not is_sec_element:
                is_sec_element = is_header_match(element, 'Source:', 'Source') or is_header_match(element, 'Note:', 'Note')
                continue

            if "Contact" in element.get_text():
                is_contact_box = True
            if element.y0 < 750: #ignore the headers
                if element.x0 < cls.left_sec_x0 and not is_contact_box:
                    left_elements.append(element)
                elif element.x0 >= cls.left_sec_x0 and not is_last_page:
                    right_elements.append(element)

        left_elements = remove_footer(left_elements)
        right_elements = remove_footer(right_elements)
        elements = left_elements + right_elements
        return elements, is_last_page, is_sec_element

    @classmethod
    def get_sections(cls, elements, **kwargs):
        cur_header = kwargs.get('cur_header', '')
        cur_section = kwargs.get('cur_section', [])
        sections = []
        is_chart, is_note_source = False, False
        
        for element in elements:
            is_note_source = element.get_text().startswith("Source:") or element.get_text().startswith("Note:")
            
            if not is_chart: 
                is_chart = element.get_text().startswith("Chart")
            if is_note_source: 
                is_chart = False
            
            if not (is_chart or is_note_source):
                if "DeviceRGB" not in get_char_colors(element):
                    cur_section.append(element.get_text())
                    continue

                if len(cur_section) > 0:
                    sections.append([cur_header, clean_text(cur_section)])
                    cur_section = []

                cur_header, cur_text = cls.get_header_text(element)
                cur_section.append(cur_text)
        return sections, cur_header, cur_section
    
    @classmethod
    def join_sections(cls, json_list):
        last_header_id = None
        removed_ids = []
        for i, item in enumerate(json_list):
            if item["section_header"]!="":
                last_header_id = i 
            elif last_header_id is not None:
                json_list[last_header_id]["section_text"] += item["section_text"]
                removed_ids.append(i)
        json_list = [json_list[i] for i in np.arange(len(json_list)) if i not in removed_ids]
        return json_list

    @classmethod
    def get_header_text(cls, element: LTTextBoxHorizontal):
        header_list = []
        text_list = []
        for i in range(1, len(element)+1):
            if get_colors(list(element)[0:i]) == {(0.222, 0.178, 0.509)}:
                header_list.append(list(element)[i-1].get_text())
            else:
                text_list.append(list(element)[i-1].get_text())

        header = concat_lines(''.join(header_list))
        text = clean_text(text_list)
        return header, text

