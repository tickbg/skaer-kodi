import re
import sys
import time
import json
import urllib2
from cookielib import CookieJar
import md5

std_headers = {
    'User-Agent': 'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:52.0) Gecko/20100101 Firefox/52.0',
    'Accept-Charset': 'ISO-8859-1,utf-8;q=0.7,*;q=0.7',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-us,en;q=0.5',
}

class MediaScraper:
    BASE_URL = 'https://yesmovies.to/'

    def __init__(self):
        self._cookiejar = CookieJar()
        self._opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(self._cookiejar))
        self._genres = dict()

    def _urlopen(self, url, data=None):
        try:
            req = urllib2.Request(url, data, std_headers)
            response = self._opener.open(req)
            data = response.read()
            response.close()
            return data
        except (urllib2.URLError, http.client.HTTPException, socket.error) as err:
            print('Got error from urlopen() %s'.format(err))
        return None

    def avail_genres(self):
        if not self._genres:
            data = self._urlopen(MediaScraper.BASE_URL)
            if data:
                for r in re.finditer('<a href=\"(\S+/genre/\S+)\"'
                                     ' title=\"(\S+)\"' , data):
                    genre_name, genre_url = r.group(2), r.group(1)
                    self._genres[genre_name] = genre_url
        return self._genres

    def movies_info(self, url):
        movies = dict()
        data = self._urlopen(url)
        if data:
            for r in re.finditer('<a href=\S+ class=\"ml-mask\"' 
                                 ' title=\"(.+)\"\s+data-url=\"(\S+)\">'
                                 '\s.+\s.+<.+\s+data-original=\"(\S+)\"', data):
                info_url = MediaScraper.BASE_URL + r.group(2)
                found = re.search('(\d+)\.html', info_url)
                if found:
                    movies[r.group(1)] = {
                        'movid' : found.group(1),
                        'info_url' : info_url,
                        'img_url' : r.group(3),
                    }
        return movies

    def parse_playlist(self, json_data):
        def as_object(dct):
            streams = dict()
            if 'playlist' in dct:
                pl = dct['playlist']
                if not isinstance(pl, list):
                    raise TypeError
                sources = pl[0]['sources']
                for src in sources:
                    if src['type'] == 'video/mp4':
                        streams[src['label']] = src['file']
                if streams:
                    return streams
            return dct

        play_list = json.loads(json_data, object_hook=as_object)
        return play_list

    def search(self, title):
        movies = dict()
        m = md5.new()
        m.update(title)
        data = self._urlopen(MediaScraper.BASE_URL + 'ajax/movie_suggest_search.html',
                            "keyword=" + title + "&hash=" + m.hexdigest())
        pattern = re.compile('search\\\/(\S+)\\\\"')
        match = pattern.search(data)
        if match:
            print(MediaScraper.BASE_URL + 'search/' + match.group(1))
            movies = self.movies_info(MediaScraper.BASE_URL + 'search/' + match.group(1))
        return movies

    def media_url(self, movid):
        data = self._urlopen(MediaScraper.BASE_URL + 'ajax/v4_movie_episodes' + '/' + movid)
        if data is not None:
            # Extract all source ids 
            # representing different media sources or episodes.
            # A valid source id is the one having the data-id atribute.
            source_ids = []
            for r in re.finditer('data-server=\\\\"\d+\\\\".data-id=\\\\"(\d+)', data):
                source_ids.append(r.group(1))
            if not source_ids:
                return None
            # Second step of Yesmovies API 
            # is to extract security tokens _x nad _y for every media source.
            for eid in source_ids:
                data = self._urlopen(
                    MediaScraper.BASE_URL + 'ajax/movie_token?eid=' + eid + 
                    '&mid=' + movid + '&_=' + str(int(time.time())))
                result = re.match('_x=\'(\S+)\', _y=\'(\S+)\'', data)
                if result is not None:
                    data = self._urlopen(
                        MediaScraper.BASE_URL + 'ajax/movie_sources/' + eid +
                        '?x=' + result.group(1) + '&y=' + result.group(2))
                    if data:
                        plist = self.parse_playlist(data)
                        return plist
        return None
