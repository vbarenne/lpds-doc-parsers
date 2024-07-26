__author__ = ['Pei Kaiyu', 'Jia Chenlong']
__version__ = 'v2.0'


import os
import time
from decouple import config
from openai import AzureOpenAI
import pandas as pd
from data_connector.base_connector import BaseConnector
from data_connector.rw_connector import RWConnector
from data_connector.cio_connector import CIOConnector
from data_connector.wire_connector import WireConnector
from data_connector.rf_connector import RFConnector
from utils.pdf_helper.doc_helper import get_name_from_path


class DataProcessPipeline:
    file_parser = {'cio': CIOConnector(), 'wire': WireConnector(), 'rw': RWConnector(), 'rf': RFConnector(),
                   'base': BaseConnector()}
    client = AzureOpenAI(api_key=config("OPENAI_API_KEY"), api_version=config('CHAT_API_VERSION', '2023-03-15-preview'),
                         azure_endpoint=f"https://{config('OPENAI_SERVICE')}.openai.azure.com")
    embedding_model = config('EMBEDDING_MODEL')

    @classmethod
    def get_all(cls, fp_list, file_type=None):
        all_json, failed_files = cls.get_json(fp_list, file_type)
        all_embedded_json = cls.add_embedding(all_json)
        return all_embedded_json, failed_files

    @classmethod
    def get_json(cls, fp_list, parser='base'):
        data_connector = cls.file_parser[parser]
        json_list = []
        failed_fp_list = []
        for fp in fp_list:
            try:
                json_list += data_connector.get_json_all(fp)
            except Exception as e:
                print(f'The file cannot be processed by {parser} data connector due to the error: {e}')
                failed_fp_list.append(get_name_from_path(fp))
                continue
        return json_list, failed_fp_list
    
    @classmethod
    def add_embedding(cls, json_file_list) -> dict:
        frames = []
       
        for json_file in json_file_list:
            input_df = pd.json_normalize(json_file)
            input_df = input_df.dropna(subset=['section_text'])
            input_df['section_text_with_metadata'] = \
                'publication_date: ' + input_df['publication_date'] + '\n' \
                + 'series: ' + input_df['series'] + '\n' \
                + 'document_name: ' + input_df['document_name'] + '\n' \
                + 'section_header: ' + input_df['section_header'] + '\n' \
                + input_df['section_text']
            input_df['section_text_with_metadata_embedding'] = input_df['section_text_with_metadata'].map(cls.get_embedding)
            frames.append(input_df)

        result = pd.concat(frames)
        print('Embedding data completed')
        return result.to_json(orient='records')

    @classmethod
    def get_embedding(cls, text: str) -> list[float]:
        retry = 0
        while retry < 10:
            try:
                result = cls.client.embeddings.create(model=cls.embedding_model, input=text)
                embedding = result.data[0].embedding
                return embedding
            except Exception as e:
                print(f"An error occurred: {e}")
                # embedding = []  #
                time.sleep(2)
                retry += 1
        return []
    
