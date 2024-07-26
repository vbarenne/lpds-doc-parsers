__author__ = ['Pei Kaiyu', 'Chenlong']
__version__ = 'v2.0'

import os
from pdfminer.high_level import extract_pages
from pdfminer.layout import LTTextContainer, LTPage, LTTextBoxHorizontal
from data_connector.base_connector import BaseConnector
from utils.pdf_helper.doc_helper import get_date_from_header, get_name_from_cover, remove_legal_disclaimer, get_page_number, get_page_number_from_title
from utils.pdf_helper.text_helper import clean_text, is_text_in_font_size, concat_lines
from settings import JB_LEGAL_DISCLAIMER


class WireConnector(BaseConnector):
    doc_type = 'The Wire'
    top_story = 'TOP STORIES'
    market_update = 'MARKET UPDATE'
    market_review_forecast = 'MARKET REVIEW & FORECASTS'
    economy_market = 'ECONOMIES & MARKETS'
    economy_forecast = 'ECONOMIC FORECASTS'
    company_news = 'COMPANY NEWS'
    legal_info = 'IMPORTANT LEGAL INFORMATION'
    tech_recommendation = 'TECHNICAL RECOMMENDATIONS'
    left_sec_x0 = 100
    page_start = 2
    sec_title_font = 12

    @classmethod
    def get_json_all(cls, fp):
        pages = list(extract_pages(fp))
        json_list = []

        pub_date = get_date_from_header(pages[0])
        src_doc = os.path.basename(fp).replace('.pdf', '')
        doc_name = get_name_from_cover(cls.doc_type, pages[0])

        market_update_num = get_page_number(list(pages[0])[1])
        market_update_sec = cls.get_market_update(pages[0])
        sec_json = cls.format_section(pub_date=pub_date, src_doc=src_doc, pg_num=market_update_num,
                                      doc_name=doc_name, sec_title=cls.market_update, sec_header='',
                                      sec_text=market_update_sec, series=cls.doc_type)
        json_list.append(sec_json)

        top_stories_num = cls.get_page_number_from_font(pages, cls.top_story, cls.sec_title_font) - 1
        market_review_forecasts_num = get_page_number_from_title(pages, cls.market_review_forecast)
        json_list = cls.get_contents(pages=pages[top_stories_num: market_review_forecasts_num],
                                     cur_sec_title=cls.top_story, next_sec_title=cls.market_review_forecast,
                                     json_list=json_list, pub_date=pub_date, doc_name=doc_name, src_doc=src_doc)

        economy_market_num = cls.get_page_number_from_font(pages, cls.economy_market, cls.sec_title_font) - 1
        economic_forecasts_num = get_page_number_from_title(pages, cls.economy_forecast)
        json_list = cls.get_contents(pages=pages[economy_market_num: economic_forecasts_num],
                                     cur_sec_title=cls.economy_market, next_sec_title=cls.economy_forecast,
                                     json_list=json_list, pub_date=pub_date, doc_name=doc_name, src_doc=src_doc)

        company_news_num = cls.get_page_number_from_font(pages, cls.company_news, cls.sec_title_font) - 1
        tech_recommendation_num = get_page_number_from_title(pages, cls.tech_recommendation)
        if tech_recommendation_num:
            company_news_pages = pages[company_news_num: tech_recommendation_num]
            next_sec_title = cls.tech_recommendation
        else:
            legal_info_num = get_page_number_from_title(pages, cls.legal_info) - 1
            company_news_pages = pages[company_news_num: legal_info_num]
            next_sec_title = cls.legal_info
        json_list = cls.get_contents(pages=company_news_pages, cur_sec_title=cls.company_news,
                                     next_sec_title=next_sec_title, json_list=json_list, pub_date=pub_date,
                                     doc_name=doc_name, src_doc=src_doc)
        return json_list

    @classmethod
    def get_market_update(cls, page: LTPage):
        is_market_update = False
        market_update_sec = []
        for element in page:
            if not isinstance(element, LTTextContainer):
                continue

            if not is_market_update:
                is_market_update = element.get_text().startswith(cls.market_update)
                continue

            if element.get_text().startswith(cls.top_story):
                break

            if element.x0 < cls.left_sec_x0:
                market_update_sec.append(element.get_text())

        sec_text = clean_text(market_update_sec)
        sec_text = remove_legal_disclaimer(sec_text, JB_LEGAL_DISCLAIMER)
        return sec_text

    @classmethod
    def get_page_number(cls, element: LTTextContainer) -> int:
        return int(element.get_text().split('/')[0])

    @classmethod
    def get_page_number_from_font(cls, pages: list, title: str, font_size: int) -> int:
        for page_number, page in enumerate(pages, start=1):
            for element in page:
                if not isinstance(element, LTTextContainer):
                    continue

                if not element.get_text().startswith(title):
                    continue

                element_list = list(list(element)[0])[0:len(title)]
                if is_text_in_font_size(element_list, font_size):
                    return page_number
        return 0

    # @classmethod
    # def get_page_number_by_title(cls, pages: list, title: str) -> int:
    #     for page_number, page in enumerate(pages, start=0):
    #         for element in page:
    #             if isinstance(element, LTTextContainer) and (title in element.get_text()):
    #                 return page_number
    #     return 0

    @classmethod
    def get_contents(cls, pages, cur_sec_title, next_sec_title, json_list, pub_date, doc_name, src_doc):
        is_sec_element = False
        cur_section = []
        cur_header = ''
        page_num = 0

        for page in pages:
            elements, is_sec_element = cls.get_page_elements(page, is_sec_element=is_sec_element,
                                                             cur_sec_title=cur_sec_title, next_sec_title=next_sec_title)
            sections, cur_header, cur_section = cls.get_sections(elements, cur_section=cur_section,
                                                                 cur_header=cur_header)
            page_num = get_page_number(list(page)[1])
            for sec_header, sec_text in sections:
                sec_json = cls.format_section(pub_date=pub_date, src_doc=src_doc, pg_num=page_num, doc_name=doc_name,
                                              sec_title=cur_sec_title, sec_header=sec_header, sec_text=sec_text,
                                              series=cls.doc_type)
                json_list.append(sec_json)
        if len(cur_section) > 0:
            sec_text = clean_text(cur_section)
            sec_json = cls.format_section(pub_date=pub_date, src_doc=src_doc, pg_num=page_num, doc_name=doc_name,
                                          sec_title=cur_sec_title, sec_header=cur_header, sec_text=sec_text,
                                          series=cls.doc_type)
            json_list.append(sec_json)
        return json_list

    @classmethod
    def get_page_elements(cls, page, is_sec_element, **kwargs):
        elements = []
        cur_sec_title = kwargs.get('cur_sec_title', '')
        next_sec_title = kwargs.get('next_sec_title', '')

        for element in list(page)[cls.page_start:]:
            if not isinstance(element, LTTextBoxHorizontal):
                continue

            if not is_sec_element:
                element_list = list(list(element)[0])[0: len(cur_sec_title)]
                is_sec_element = (element.get_text().startswith(cur_sec_title) and
                                  is_text_in_font_size(element_list, cls.sec_title_font))
                continue

            if element.get_text().startswith(next_sec_title):
                break

            if element.x0 < cls.left_sec_x0:
                elements.append(element.get_text())

        return elements, is_sec_element

    @classmethod
    def get_sections(cls, elements, **kwargs):
        cur_header = kwargs.get('cur_header', '')
        cur_section = kwargs.get('cur_section', [])
        sections = []
        for element_text in elements:
            if concat_lines(element_text).isupper():
                if len(cur_section) > 0:
                    text = clean_text(cur_section)
                    text = remove_legal_disclaimer(text, JB_LEGAL_DISCLAIMER)
                    sections.append([cur_header, text])
                    cur_section = []

                cur_header = concat_lines(element_text)
                continue
            cur_section.append(element_text)
        return sections, cur_header, cur_section
