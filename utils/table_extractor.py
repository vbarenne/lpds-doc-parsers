
import os
from pdfminer.high_level import extract_pages
from pdfminer.layout import LTTextContainer, LTPage, LTTextBoxHorizontal, LTLine
from data_connector.base_connector import BaseConnector
from utils.pdf_helper.doc_helper import get_date_from_name, get_name_from_cover
from utils.pdf_helper.text_helper import is_header_match, remove_footer, get_char_colors, remove_hyphenation, concat_lines, remove_uncommon_utf8, clean_text, get_colors
import numpy as np
import pandas as pd

def table_extractor(page, ymin, ymax, xmin = -1, xmax =10000, row_lines = True, has_header = False):
    elements = [el for el in page if (el.y0 > ymin and el.y0 < ymax and el.x0 >-1 and el.x0 < 1000 and isinstance(el, LTTextBoxHorizontal))]
    table, cnt = [], []
    table_formatted = []

    # Get row delimiters 
    if row_lines: 
        row_lim = np.unique([el.y0 for el in page if (el.y0 > ymin and el.y0 < ymax and isinstance(el, LTLine))])
    else: 
        row_lim = np.unique([el.y0 for el in elements])
    row_lim = [ymax] + list(- np.sort(-np.array(row_lim))) + [ymin]

    # Get number of columns (based on majority formatting of rows)
    for i in range(len(row_lim)-1):
        ymin_row, ymax_row = row_lim[i+1], row_lim[i]
        row = [el for el in elements if (el.y0 > ymin_row and el.y0 <ymax_row)]
        cnt.append(len(row))
        table.append(row)
    n_cols = np.bincount(cnt).argmax()

    # Get column delimiters
    col_lim = np.zeros(n_cols)
    for i in range(n_cols):
        col_lim[i] = max([row[i].x1 for row in table if (len(row)==n_cols)])
    col_lim = [xmin] + list(col_lim)
    col_lim[-1] = xmax

    # Format each row in table to match the number of columns
    for row in table:   
        if len(row) == n_cols:
            table_formatted.append([clean_text(el.get_text().lower()) for el in row])
        else: 
            row_good_format = []
            for i in range(len(col_lim)-1):
                xmin_col, xmax_col = col_lim[i], col_lim[i+1]
                col_element = clean_text([el.get_text().lower() for el in row if el.x1 > xmin_col and el.x1 <= xmax_col])
                row_good_format.append(col_element)
            table_formatted.append(row_good_format)
    table_formatted = np.array(table_formatted)

    if (table_formatted[0,:]=="").all():
        table_formatted = table_formatted[1:, :]

    if has_header:
        table_formatted = pd.DataFrame(data = table_formatted[1:,1:], 
                                       columns = table_formatted[0,1:], 
                                       index = table_formatted[1:, 0])
    else: 
        table_formatted = pd.DataFrame(data = table_formatted[:,1:], 
                                       index = table_formatted[:,0])

    return table_formatted


def get_n_th_line_height(page, n):
    lines = [el.y0 for el in page if isinstance(el, LTLine)]
    return np.partition(lines, n)[n]

