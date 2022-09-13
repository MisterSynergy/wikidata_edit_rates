## Wikidata edit rate monitor ##
#
# creator: https://www.wikidata.org/wiki/User:MisterSynergy
# license: MIT License
# version: 2022-09-13
# status : beta; might crash, or contain bugs
# Python version: 3.9
#
# please use Ctrl+C to terminate the script

from json import loads
from sys import exit as sys_exit
from threading import Thread
from time import gmtime, sleep, strftime, time
from typing import Any, Dict, Optional

import pandas as pd
import requests
from pandas.core.indexing import IndexingError
from requests.exceptions import HTTPError
from sseclient import Event, SSEClient as EventSource

from config import Config


class Maxlag:
    maxlag:Dict[str, float] = { 'timestamp' : 0.0, 'lag' : 0.0 }
    maxlag_refresh:int

    def __init__(self, maxlag_refresh:int) -> None:
        self.maxlag_refresh = maxlag_refresh
        self.update_maxlag()

    def update_maxlag(self) -> None:
        t_now = time()

        if t_now-self.maxlag.get('timestamp', 0) <= self.maxlag_refresh:
            return

        response = requests.get(
            url=CONFIG.wikidata_api_endpoint,
            params={
                'action' : 'query',
                'titles' : 'Q1',
                'format' : 'json',
                'maxlag' : '-1'
            },
            headers={
                'User-Agent': f'{requests.utils.default_headers()["User-Agent"]}' \
                                f' (Wikidata bot by User:{CONFIG.username}; mailto:{CONFIG.email})'
            }
        )
        payload = response.json()

        self.maxlag = {
            'timestamp' : t_now,
            'lag' : float(payload.get('error', {}).get('lag', 0))
        }


class EventManager:
    # currently unused parameters: id, namespace, title, type, minor, patrolled
    data:pd.DataFrame = pd.DataFrame({
        'timestamp' : [],
        'ts' : [],
        'user' : [],
        'b' : [],
        'newlen' : []
    })

    total_edits:Optional[int] = None
    total_len:Optional[int] = None
    different_users:int

    top_list:Optional[pd.DataFrame] = None

    def process_event(self, event:Event):
        if event.event != 'message':
            return

        try:
            change = loads(event.data)
        except ValueError:
            return

        if change.get('wiki', '') != 'wikidatawiki':
            return

        # ignore all actions except edits and page creations
        if change.get('type') not in [ 'edit', 'new' ]:
            return

        self._add_event(change)

    def _add_event(self, change:Dict[str, Any]) -> None:
        new_event = pd.DataFrame(
            data={  
                'timestamp' : [ int(change.get('timestamp', 0)) ],
                'ts' : [ pd.to_datetime(int(change.get('timestamp', 0)), unit='s') ], # not in use at the moment
                'user' : [ change.get('user', '') ],
                'b' : [ { True : 'b', False : '' }[change.get('bot', False)] ],
                'newlen' : [ int(change.get('length', {}).get('new', 0)) ]
            }
        )
        self.data = pd.concat(
            objs=[
                self.data,
                new_event
            ],
            ignore_index=True
        )

    def _purge_old_events(self, timeframe:int=60) -> None:
        filt = self.data['timestamp'] > time()-timeframe

        try:
            self.data.drop( # drop old entries from dataframe
                index=self.data.loc[~filt].index,
                inplace=True
            )
        except IndexingError as exception:
            print(exception)

    def _calc_total_edits(self) -> None:
        try:
            self.total_edits = self.data.shape[0]
        except IndexingError:
            self.total_edits = None

    def _calc_total_len(self) -> None:
        try:
            self.total_len = int(self.data['newlen'].sum())
        except IndexingError:
            self.total_len = None

    def _make_top_list(self) -> None:
        # two columns: user name, number of edits
        head_list:pd.Series = self.data['user'].value_counts()

        # two columns: user name, bot status
        bot_list:pd.DataFrame = self.data[['user', 'b']].drop_duplicates(
            subset='user',
            keep='first' # bot status is whatever is found first, in case an account is both bot and no bot
        )
        bot_list.set_index('user', inplace=True)

        # two columns: user name, new content lenght
        user_newlen:pd.DataFrame = self.data.groupby(by=['user']).apply(
            lambda x : format_len(int(x.newlen.sum()))
        )

        self.different_users = bot_list.shape[0]

        try:
            self.top_list = pd.concat(
                [head_list, bot_list, user_newlen],
                axis='columns',
                sort=False
            ).head(CONFIG.top_user_num)
        except IndexingError as exception:
            print(f'IndexingError Exception "{exception}"; no topList')
            self.top_list = None
        except ValueError as exception:
            print(f'ValueError Exception "{exception}"; no topList')
            self.top_list = None
        except Exception as exception:
            print(f'Exception "{exception}"; no topList')
            self.top_list = None
        else:
            self.top_list.rename(
                columns={ 'user' : 'edit rate', 0 : 'volume' },
                inplace=True
            )

    def make_snapshot(self, timeframe:int=60) -> None:
        self._purge_old_events(timeframe)
        self._calc_total_edits()
        self._calc_total_len()
        self._make_top_list()


class EventStream:
    dispatch_target:EventManager
    thread:Thread
    stream_is_on:bool = False

    def __init__(self, dispatch_target:EventManager) -> None:
        self.dispatch_target = dispatch_target
        self._start_stream()

    def _start_stream(self) -> None:
        self.thread = Thread(target=self.read_stream)
        self.thread.daemon = True # use Ctrl+C to terminate the script
        self.thread.start()

    def check_stream(self) -> None:
        if self.stream_is_on is True: # still fine
            return

        print('Restart stream ...')
        self.thread.join()
        sleep(1)
        self._start_stream()

    def read_stream(self) -> None:
        self.stream_is_on = True

        try:
            for event in EventSource(CONFIG.rc_stream_source):
                self.dispatch_target.process_event(event)
        except HTTPError as exception:
            print(exception)
            self.stream_is_on = False
            return
        except Exception as exception:
            print(exception)
            self.stream_is_on = False
            sys_exit(1)


def format_len(length:int=0) -> str:
    if length <= 1024:
        return f'{length:d}   B'

    if length <= 1024*1024:
        return f'{round(length/1024, 2):,.2f} kiB'

    return f'{round(length/1024/1024, 2):,.2f} MiB'


def main() -> None:
    event_manager = EventManager()
    event_stream = EventStream(dispatch_target=event_manager)
    maxlag = Maxlag(CONFIG.maxlag_refresh)

    while True: # reporting to console
        thread_read = Thread(target=event_manager.make_snapshot, args=[ CONFIG.timeframe ])
        thread_maxlag = Thread(target=maxlag.update_maxlag)

        thread_read.start()
        thread_maxlag.start()

        thread_read.join()

        print(f'\n== {strftime("%Y-%m-%d %H:%M:%S", gmtime())} (UTC) ==')
        print(f'Maxlag: {round(maxlag.maxlag.get("lag", 0), 1)} (requested {round(time()-maxlag.maxlag.get("timestamp", 0))} s ago)')

        if event_manager.total_edits is not None:
            print(f'Total edits in past {CONFIG.timeframe} s: {event_manager.total_edits} by {event_manager.different_users} users')
        else:
            print('Skip total_edits')

        if event_manager.total_len is not None:
            print(f'Total new len in past {CONFIG.timeframe} s: {format_len(event_manager.total_len)}')
        else:
            print('Skip total_len')

        print(f'Top {CONFIG.top_user_num} users by edit rate (1/min):')
        print(event_manager.top_list)

        event_stream.check_stream()

        sleep(CONFIG.sleep_per_step)
        thread_maxlag.join()

    event_stream.thread.join()

if __name__=='__main__':
    CONFIG = Config.load()
    try:
        main()
    except KeyboardInterrupt:
        print('\n\nStopped')
