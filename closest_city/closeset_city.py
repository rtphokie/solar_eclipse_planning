import csv
import pyproj
import pickle
from pprint import pprint

geodesic = pyproj.Geod(ellps='WGS84')


def getcities(filename='closest_city/uscities.csv', minpop=10000):
    fh = open(filename, 'rt')
    csv_reader = csv.reader(fh, dialect='excel', quotechar='"')
    data = {}
    bucketed_data = {}
    radius = 1000
    for row in csv_reader:
        if int(row[8]) > minpop:
            data[f"{row[0]} {row[2]}"] = (float(row[6]), float(row[7]), int(row[8]))
    fh.close()
    return data


def closest_city(lat, lng):
    lat = round(lat, 4)
    lng = round(lng, 4)
    picklefile = 'closest_city/closest_city_cache.pkl'
    cachekey = f"{lat}|{lng}"
    try:
        fp = open(picklefile, "rb")
        cache = pickle.load(fp)
        fp.close()
    except Exception as e:
        print(e)
        cache = {}
    if cachekey not in cache.keys():
        data = getcities()
        result = None
        found = False
        iter = 0
        for maxradius in range(100000, 2000000, 100000):  # ~ half the equitorial diameter
            iter += 1
            if found:
                break
            possibles = {}
            details = {}
            for minpop in range(18000000, 1, -100000):
                iter += 1
                if found:
                    break
                for city in sorted(data, key=lambda x: data[x][2], reverse=True):
                    if data[city][2] < minpop:
                        continue
                    fwd_azimuth, back_azimuth, distance = geodesic.inv(lng, lat, data[city][1], data[city][0])
                    if distance <= maxradius:
                        possibles[city] = distance
                        details[city] = {'az': back_azimuth, 'dist': distance}
                if len(possibles) > 0:
                    possibles = sorted(possibles, key=possibles.get, reverse=False)
                    result = possibles[0]
                    found = True
                    break

        # if the cities are loaded, it will find someting within a 2 million km radius
        cache[cachekey] = (result, data[result][0], data[result][1],
                           details[result]['az'], details[result]['dist'] * 0.000621371)
        # save to cache, this is expensive
        fh = open(picklefile, "wb")
        pickle.dump(cache, fh)
        fh.close()
    return cache[cachekey]

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

