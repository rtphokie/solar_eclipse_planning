import googlemaps
from config import API_key
from zipfile import ZipFile
import pickle
from pprint import pprint
from pykml import parser
from scipy.spatial import distance
import haversine


def get_central_path_coords(kmzfilename='TSE_2024_04_08.kmz', name='Central Line'):
    '''
    parses a given KML file (default's to the 2024 Eclipse, provided by Xavier M. Jubier)
    http://xjubier.free.fr/en/index_en.html is a good resource

    :param kmzfilename: filename for the KMZ file
    :param name: name of the placemark line describing the central path
    :return: list of longitude, latitude tuples
    '''
    kmz = ZipFile(kmzfilename, 'r')
    kmlfilename = None
    for o in kmz.filelist:
        if o.filename.endswith('.kml'):
            kmlfilename = o.filename
    if kmlfilename is None:
        raise FileNotFoundError(f'kml file not found in {kmzfilename} zip file')
    kml_str = kmz.open(kmlfilename, 'r').read()

    doc = parser.fromstring(kml_str)

    coords = []
    for e in doc.findall('.//{http://www.opengis.net/kml/2.2}Placemark'):
        if e.name != name:
            continue
        for pair in str(e.LineString.coordinates).split(' '):
            if len(pair) > 5:
                lng, lat, alt = pair.split(',')
                coords.append([float(lat), float(lng)])
    if len(coords) == 0:
        raise LookupError(f"coordinates not found for path named {name} in {kmzfilename}.")
    return coords


def closest_node(coords_1, nodes):
    import geopy.distance

    dists = []
    for coords_2 in nodes:
        dists.append(geopy.distance.distance(coords_1, coords_2).km)
    min_dist = min(dists)
    min_dist_index = dists.index(min_dist)

    return nodes[min_dist_index], min_dist * 0.621371


import googlemaps
from config import API_key

gmaps = googlemaps.Client(key=API_key)


def getdrivingdistance(origin, dest, line=2024):
    filename = 'gmaps_distance.pkl'
    key = (origin[0], origin[1], dest[0], dest[1], line)
    data = {}
    try:
        file = open(filename, 'rb')
        data = pickle.load(file)
        file.close()
        if key in data.keys():
            # print('from cache')
            result = data[key]
        else:
            result = None
    except:
        result = None
    if result is None:
        print("from google")
        result = gmaps.distance_matrix(origin, dest, mode='driving')
        file = open(filename, 'wb')
        data[key] = result
        pickle.dump(data, file)
        file.close()
    return result


def get_result(origin, dest, pt, coordinatelist):
    result = getdrivingdistance(origin, dest, line=2024)
    result['destination_coordinates'] = dest
    if 'USA' not in result['destination_addresses'][0]:
        # find a navicable point along the line, within the US, usually because of water
        newpt = pt
        it = 0
        previous_country = None
        while 'USA' not in result['destination_addresses'][0] and it < 25:
            if 'Mexico' in result['destination_addresses'][0] or previous_country == 'Mexico':
                previous_country = 'Mexico'
                newpt += 5
            else:
                previous_country = 'Canada'
                newpt -= 5
            print(newpt)
            dest = (coordinatelist[newpt][0], coordinatelist[newpt][1])
            result = getdrivingdistance(origin, dest, line=2024)
            result['destination_coordinates'] = dest
            it += 1
    return result


def binary_search_closest_driving_distance(origin, coordinatelist):
    # gmaps = googlemaps.Client(key=API_key)
    coordinatelist = get_central_path_coords(kmzfilename='TSE_2024_04_08.kmz')
    # some sensible bounds for the 2024 path, get us close to the US borders
    low = 488
    high = 743
    i = 0
    width = high - low

    prevmid=999999999
    while width > 2:
        i += 1
        width = high - low
        mid = round((width / 2) + low)
        results = []
        times = []
        for n, pt in enumerate([low, mid, high]):
            dest = (coordinatelist[pt][0], coordinatelist[pt][1])
            result = get_result(origin, dest, pt, coordinatelist)
            results.append(result)
            times.append(result['rows'][0]['elements'][0]['duration']['value'])
        if prevmid < times[1]:
            # retry with the other opposite half if driving times actually increased
            if search=='down':
                low=mid
            else:
                high=mid
            continue
        else:
            prevmid=times[1]
            deltaa = abs(times[0] - times[1])
            deltab = abs(times[1] - times[2])
            if deltaa < deltab:
                high=mid
                search = 'down'
            else:
                low=mid
                search = 'up '
        print( f"{i:2} {width:3} {search} |{results[0]['destination_addresses'][0]} | {results[1]['destination_addresses'][0]}  | {results[2]['destination_addresses'][0]} {times}")

        # print(search, width, coordinatelist[mid], results[0]['destination_addresses'][0])
    mintime=min(times)
    minindex=times.index(mintime)
    return (results[minindex])
