import requests
import time
import requests_cache
import arrow
import re
import math
import ephem
import json
import re
from fireballalerts.closeset_city import closest_city
from pprint import pprint
import pyproj
from utils.mylogger import mylogging
import statistics

logger = mylogging('fireball', 'fireball.log')

geodesic = pyproj.Geod(ellps='WGS84')

headers = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.95 Safari/537.36'}

from fireballalerts.config import api_key, rapidapi_key

BASEURL = 'https://www.amsmeteors.org/members/api/open_api'
datetime_format = 'YYYY-MM-DD HH:mm:ss'


def get_direction_from_bearing(bearing):
    # meteorological 16 points

    pattern = ['YYX', 'YX', 'XYX']
    sectors = ['N'] + [w.replace('Y', 'N').replace('X', 'E') for w in pattern]
    sectors += ['E'] + [w.replace('Y', 'S').replace('X', 'E') for w in pattern]
    sectors += ['S'] + [w.replace('Y', 'S').replace('X', 'W') for w in pattern]
    sectors += ['W'] + [w.replace('Y', 'N').replace('X', 'W') for w in pattern]
    sectors += ['N']

    index = bearing % 360
    index = round(index / 22.5, 0)

    return sectors[int(index)]


def _get(uri_raw, format='json'):
    url = BASEURL + uri_raw + f"&format=json&api_key={api_key}"
    r = requests.get(url)
    logger.debug(f"from cache {r.from_cache} {url}")
    result = None
    if format == 'json':
        try:
            data = r.json()
        except Exception as e:
            raise Exception(e)
    else:
        result = r.text
    if r.status_code == 200:
        result = data
    elif r.status_code == 400:
        raise Exception(f"error in query {data['errors']}\n{url}")
    elif r.status_code == 405:
        pass
    else:
        raise Exception(f"unhandled status code {r.status_code}")
    return result


def recent_reports(hours=24, pending_only=0, min_reports=4, utc_now=arrow.utcnow()):
    # Use a breakpoint in the code line below to debug your script.
    utc_now = utc_now.replace(minute=0, second=0, microsecond=0)
    utc_now = utc_now.shift(hours=1)
    logger.info(f"querying reports in the {hours} hrs since {utc_now}")
    datatoreturn = {'events': {}, 'pending': []}
    utc_then = utc_now.shift(hours=hours * -1)
    uri = f'/get_close_reports?start_date={utc_then.format(datetime_format)}&end_date={utc_now.format(datetime_format)}&pending_only={pending_only}'
    data = _get(uri)
    results = data['result']
    cnt_events = 0
    durations = {}
    for result_id, result_data in results.items():
        regexpattern_aggregated = r"Report #(\d+)\-(\d+)\s(\w+)"
        regexpattern_pending = r"Report (\d+)"
        m = re.search(regexpattern_aggregated, result_id)
        result_data['ID'] = result_id
        if m:
            event_id = m.group(1)
            year = m.group(2)
            iter = m.group(3)
        else:
            m = re.search(regexpattern_pending, result_id)
            event_id = 'Pending'
            if m:
                year = arrow.utcnow().year
            else:
                raise ValueError(f"{result_id} year not found")

        if event_id == 'Pending':
            datatoreturn['pending'].append(result_data)
        else:
            # (-171.791110603, 18.91619, -66.96466, 71.3577635769))
            # 50 US states bounding box
            if float(result_data['latitude']) < 18 or float(result_data['latitude']) > 71.4:
                continue
            if float(result_data['longitude']) < -171.8 or float(result_data['longitude']) > -66.964:
                continue
            eventidstr = f"{event_id}|{year}"
            if eventidstr not in datatoreturn['events'].keys():
                datatoreturn['events'][eventidstr] = {'reports': [],
                                                      'event_id': event_id,
                                                      'year': year,
                                                      'event': None}
            datatoreturn['events'][eventidstr]['reports'].append(result_data)
            if eventidstr != 'Pending' and eventidstr not in durations.keys():
                durations[eventidstr] = []
            if eventidstr != 'Pending':
                durations[eventidstr].append(result_data['duration'])
    for eventidstr, data in datatoreturn['events'].items():
        if len(data['reports']) >= min_reports:
            datatoreturn['events'][eventidstr]['event'] = get_event(data['year'], data['event_id'])
            obj = datatoreturn['events'][eventidstr]['event']
            if datatoreturn['events'][eventidstr]['event'] is None:
                continue
            cnt_events += 1
            if eventidstr in durations.keys():
                datatoreturn['events'][eventidstr]['event']['durations'] = durations[eventidstr]
            if eventidstr in durations.keys() and len(durations[eventidstr]) >= 3:
                datatoreturn['events'][eventidstr]['event']['mean_duration'] = statistics.median_low(
                    durations[eventidstr])
            else:
                datatoreturn['events'][eventidstr]['event']['mean_duration'] = None

    fp = open('recent.json', 'w')
    json.dump(datatoreturn, fp, indent=4)
    fp.close()
    logger.info(f"event info gathered for {cnt_events} of {len(datatoreturn['events'])}")
    return datatoreturn


def get_event(year, event_id, threshold=500):
    requests_cache.install_cache('event_cache', backend='sqlite', expire_after=7200)
    uri = f'/get_event?event_id={event_id}&year={year}'
    data = _get(uri, format='json')
    result = None
    logger.debug(f"getting event {year} {event_id}")
    if data is not None and 'result' in data:
        result = list(data['result'].values())[0]
        if result['start_lat'] != 0 and result['start_lat'] != 0 and result['end_lat'] != 0 and result['end_lat'] != 0:
            result['videos'] = get_video(year, event_id)
            result['url'] = f"https://fireball.amsmeteors.org/members/imo_view/event/{year}/{event_id}"
            result['mid_alt'] = round((result[f'start_alt'] + result[f'end_alt']) / 2)
            result['mid_lat'], result['mid_long'] = midpoint((result['start_lat'], result['start_long']),
                                                             (result['end_lat'], result['end_long']))
            result['footprint_r_km'] = round(3.56972 * math.sqrt(result['mid_alt']))
            result['closest_city'], city_lat, city_lon, result['closest_city_bearing'], dist = closest_city(
                result['mid_lat'], result['mid_long'])
            result['closest_city_dist_mi'] = round(dist / 10) * 10
            result['closest_city_direction'] = get_direction_from_bearing(result['closest_city_bearing'])
        else:
            result = None

    return result


def get_video(year, event):
    videos = None
    url = f"https://fireball.amsmeteors.org/members/imo_view/event/{year}/{event}"
    r = requests.get(url, headers=headers)
    logger.debug(f"from cache {r.from_cache} {url}")
    regex = '\/members\/imo_video\/view_video\?video_id=(\d+)'
    rows = r.text.split("col-xs-6 col-sm-3 post thumb-gal")
    for row in rows:
        m = re.search(regex, row)
        if m:
            if videos is None:
                videos = []
            videos.append(f"https://fireball.amsmeteors.org{m.group(0)}")
    return videos


def warning_email(filename='astroreport.ini'):
    import configparser
    config = configparser.ConfigParser()
    config.read(filename)
    reports_lastweek = recent_reports(hours=48)
    dist = {}

    for station in config.sections():
        lines = []
        # gather distances
        dist = {}
        dir = {}
        for event_id, data in reports_lastweek['events'].items():
            if 'event' in data.keys() and data['event'] is not None:
                fwd_azimuth, back_azimuth, distance = geodesic.inv(config[station]['lon'],
                                                                   config[station]['lat'],
                                                                   data['event']['mid_long'],
                                                                   data['event']['mid_lat'])

                dist[event_id] = round(round(distance / 1000) / 10) * 10
                dir[event_id] = get_direction_from_bearing(fwd_azimuth)
        # iterate from closest event to furthest
        for event_id, _ in sorted(dist.items(), key=lambda kv: kv[1]):
            event_data = reports_lastweek['events'][event_id]['event']
            utc = arrow.get(event_data['avg_date_utc'] + "+00:00")
            distratio = dist[event_id] / event_data['footprint_r_km']
            if distratio > 1:
                continue
            else:
                index = distratio * 5
                visiblity_messages = ['yes', 'probably', 'maybe', 'maybe', 'doubtful', 'doubtful']
                position_messages = ['nearly overhead', f'high in the {dir[event_id]} sky', f'mid {dir[event_id]} sky',
                                     f'low in the {dir[event_id]} sky',
                                     f'just above the {dir[event_id]} horizon',
                                     f'just above the {dir[event_id]} horizon']
                visible = visiblity_messages[round(index)] + ', ' + position_messages[round(index)]
                print(station, event_id, distratio, visible)
            # lines.append(f"<TD>{visible}</TD>")


def read_config(filename='astroreport.ini'):
    import configparser
    config = configparser.ConfigParser()
    config.read(filename)
    reports_lastweek = recent_reports(hours=24 * 8)

    for station in config.sections():
        station_city, station_lat, station_lon, station_tz = config[station]['city'], config[station]['lat'], \
                                                             config[station]['lon'], config[station]['tz']
        lines = fireball_report(reports_lastweek, station_city, station_lat, station_lon, station_tz)
        fp = open('html/foo.html', 'w')
        fp.writelines("\n".join(lines))
        fp.close()


def fireball_report(reports_lastweek, station_city, station_lat, station_lon, station_tz):
    lines = []
    # gather distances
    dist = {}
    dir = {}
    for event_id, data in reports_lastweek['events'].items():
        if 'event' in data.keys() and data['event'] is not None:
            fwd_azimuth, back_azimuth, distance = geodesic.inv(station_lon, station_lat, data['event']['mid_long'],
                                                               data['event']['mid_lat'])

            dist[event_id] = round(round(distance / 1000) / 10) * 10
            dir[event_id] = get_direction_from_bearing(fwd_azimuth)
    # iterate from closest event to furthest
    for event_id, _ in sorted(dist.items(), key=lambda kv: kv[1]):
        event_data = reports_lastweek['events'][event_id]['event']
        if len(lines) == 0:
            lines.append(
                f"<TABLE border=1>\n  <TR><TH>{station_tz}</TH><TH>duration (sec)</TH><TH>reports</th><th>location</th><th>visible from {station_city}</th><th>video</th></TR>")
        utc = arrow.get(event_data['avg_date_utc'] + "+00:00")
        lines.append(f"   <TR><TD>{utc.to(station_tz).format('YYYY-MM-DD HH:mm')}</TD>")
        if 'mean_duration' in event_data.keys() and event_data['mean_duration'] is not None:
            lines.append(f"<TD align=center>{float(event_data['mean_duration']):.1f}</TD>")
        else:
            lines.append(f"<td></td>")
        lines.append(f"<TD align=center>{event_data['nbre_total_reports']}</TD>")
        lines.append(
            f"<TD><A HREF=\"{event_data['url']}\">{event_data['closest_city_dist_mi']} mi {event_data['closest_city_direction']} of {event_data['closest_city']}</A></TD>")
        distratio = dist[event_id] / event_data['footprint_r_km']
        if distratio > 1:
            visible = ""
        else:
            index = distratio * 5
            visiblity_messages = ['yes', 'probably', 'maybe', 'maybe', 'doubtful', 'doubtful']
            position_messages = ['nearly overhead', f'high in the {dir[event_id]} sky', f'mid {dir[event_id]} sky',
                                 f'low in the {dir[event_id]} sky',
                                 f'just above the {dir[event_id]} horizon', f'just above the {dir[event_id]} horizon']
            visible = visiblity_messages[round(index)] + ', ' + position_messages[round(index)]
        lines.append(f"<TD>{visible}</TD>")
        videos = []
        if event_data['videos'] is not None:
            for i, url in enumerate(event_data['videos']):
                videos.append(f"<A HREF=\"{url}\">#{i + 1}</A>")
        lines.append(f"<TD>{' '.join(videos)}</TD>")
        lines.append(f"</TR>\n")
    if len(lines) > 0:
        lines.append("</TABLE>")
    return lines


def midpoint(p1, p2):
    lat1, lat2 = math.radians(p1[0]), math.radians(p2[0])
    lon1, lon2 = math.radians(p1[1]), math.radians(p2[1])
    dlon = lon2 - lon1
    dx = math.cos(lat2) * math.cos(dlon)
    dy = math.cos(lat2) * math.sin(dlon)
    lat3 = math.atan2(math.sin(lat1) + math.sin(lat2),
                      math.sqrt((math.cos(lat1) + dx) * (math.cos(lat1) + dx) + dy * dy))
    lon3 = lon1 + math.atan2(dy, math.cos(lat1) + dx)
    return (math.degrees(lat3), math.degrees(lon3))


if __name__ == '__main__':
    pass
