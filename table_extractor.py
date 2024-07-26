# fp_switch = './publications/cEQ Switch Idea (INGA-ANB) [2024-04-15].pdf'
# pages = list(extract_pages(fp_switch))
# page = pages[1]


# fp = "publications/Equity Top Picks (2024-05-16).pdf"
# pages = list(extract_pages(fp))
# page = pages[5]
# ymin, ymax = 100, 500


import os
from pdfminer.high_level import extract_pages
from pdfminer.layout import LTTextContainer, LTPage, LTTextBoxHorizontal, LTLine
from data_connector.base_connector import BaseConnector
from utils.pdf_helper.doc_helper import get_date_from_name, get_name_from_cover
from utils.pdf_helper.text_helper import is_header_match, remove_footer, get_char_colors, remove_hyphenation, concat_lines, remove_uncommon_utf8, clean_text, get_colors
import numpy as np
import pandas as pd

def table_extractor(page, ymin, ymax, xmin = -1, xmax =10000):
    elements = [el for el in page if (el.y0 > ymin and el.y0 < ymax and el.x0 >-1 and el.x0 < 1000 and isinstance(el, LTTextBoxHorizontal))]
    table, cnt = [], []
    row_lines = True
    table_good_format = []
    xmin = -1 
    xmax= 1000
    if row_lines: 
        rows_y = np.unique([el.y0 for el in page if (el.y0 > ymin and el.y0 < ymax and isinstance(el, LTLine))])
    else: 
        rows_y = np.unique([el.y0 for el in elements])

    rows_y = [ymax] + list(- np.sort(-np.array(rows_y))) + [ymin]

    # Get the number of columns of the table (based on majority formatting of rows)
    for i in range(len(rows_y)-1):
        y0, y1 = rows_y[i+1], rows_y[i]
        row = [el for el in elements if (el.y0 > y0 and el.y0 <y1)]
        cnt.append(len(row))
        table.append(row)
    n_cols = np.bincount(cnt).argmax()
    col_end = np.zeros(n_cols)

    # Get delimiters of columns (xmin, xmax)
    for row in table:
        if len(row)== n_cols:
            for i, item in enumerate(row):
                if item.x1> col_end[i]:
                    col_end[i]= item.x1 

    col_end = [xmin] + list(col_end)
    col_end[-1] = xmax

    # Format each row in table to match the number of columns
    for row in table:   
        if len(row) == n_cols:
            table_good_format.append([clean_text(el.get_text()) for el in row])
        else: 
            row_good_format = []
            for i in range(len(col_end)-1):
                x0, x1 = col_end[i], col_end[i+1]
                col_element = clean_text([el.get_text() for el in row if el.x1 > x0 and el.x1 <= x1])
                row_good_format.append(col_element)
            table_good_format.append(row_good_format)

    return table_good_format