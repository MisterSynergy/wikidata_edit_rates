import json
import sys
from dataclasses import dataclass, asdict
from json.decoder import JSONDecodeError
from typing import TypeVar


C = TypeVar('C', bound='Config')
CONFIG_FILE = './config.json'


@dataclass(frozen=True)
class Config:
    sleep_per_step : int
    timeframe : int
    maxlag_refresh : int
    top_user_num : int
    username : str
    email : str
    rc_stream_source : str
    wikidata_api_endpoint : str

    def __post_init__(self):
        if len(self.email) == 0:
            sys.exit(f'No email address defined in {CONFIG_FILE}')
        
        if len(self.username) == 0:
            sys.exit(f'No username defined in {CONFIG_FILE}')

    @classmethod
    def load_from_json(cls:type[C]) -> C:
        with open(CONFIG_FILE, mode='r', encoding='utf8') as file_handle:
            try:
                params = json.load(file_handle)
            except JSONDecodeError as exception:
                print(exception)
                sys.exit(f'Cannot read config in {CONFIG_FILE}')
        
        config = cls(**params)
        return config

    @classmethod
    def load(cls:type[C]) -> C:
        return cls.load_from_json()
