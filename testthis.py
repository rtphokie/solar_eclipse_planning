import unittest
from eclipse_central_line_calc import get_central_path_coords, closest_node, getdrivingdistance, \
    binary_search_closest_driving_distance
from closest_city.closeset_city import closest_city, get_direction_from_bearing
from pprint import pprint


class MyTestCase(unittest.TestCase):
    def test_something(self):
        coordinatelist = get_central_path_coords(kmzfilename='TSE_2024_04_08.kmz')
        self.assertGreaterEqual(len(coordinatelist), 800)

    def test_closest_point(self):
        target = (-78.0, 35)
        coordinatelist = get_central_path_coords(kmzfilename='TSE_2024_04_08.kmz')
        foo = closest_node(target, coordinatelist)
        print(foo)

    def test_cities(self):
        lon = -79.382600861057
        lat = 41.473295527025
        city, city_lat, city_lon, bearing, dist_mi = closest_city(lat, lon)
        dist_mi = (round(dist_mi / 10)) * 10
        print(city, city_lat, get_direction_from_bearing(bearing), dist_mi)
        # lon=  -106.64

    def test_closest_to_path(self):
        target = (35.0, -78.0)
        coordinatelist = get_central_path_coords(kmzfilename='TSE_2024_04_08.kmz')
        foo, dist = closest_node(target, coordinatelist)
        city, city_lat, city_lon, bearing, dist_mi = closest_city(foo[0], foo[1])
        print(foo, city, dist)

    def test_Raleigh(self):
        origin = (35.7796, -78.6382)
        coordinatelist = get_central_path_coords(kmzfilename='TSE_2024_04_08.kmz')
        result = binary_search_closest_driving_distance(origin, coordinatelist)
        pprint(result)
        self.assertAlmostEqual(result['destination_coordinates'][0], 40.44, 2)
        self.assertAlmostEqual(result['destination_coordinates'][1], -84.25, 2)

    def test_Dalas(self):
        origin = (32.7767, -96.7970)
        coordinatelist = get_central_path_coords(kmzfilename='TSE_2024_04_08.kmz')
        result = binary_search_closest_driving_distance(origin, coordinatelist)
        pprint(result)
        self.assertAlmostEqual(result['destination_coordinates'][0], 32.57, 2)
        self.assertAlmostEqual(result['destination_coordinates'][1], -96.35, 2)


    def test_BollingGreen(self):
        origin = (36.9685, -86.4808)
        coordinatelist = get_central_path_coords(kmzfilename='TSE_2024_04_08.kmz')
        result = binary_search_closest_driving_distance(origin, coordinatelist)
        pprint(result)
        self.assertAlmostEqual(result['destination_coordinates'][0], 37.82479, 2)
        self.assertAlmostEqual(result['destination_coordinates'][1],  -88.98, 2)


    def test_Boston(self):
        origin = (42.36, -71.13)
        coordinatelist = get_central_path_coords(kmzfilename='TSE_2024_04_08.kmz')
        result = binary_search_closest_driving_distance(origin, coordinatelist)
        pprint(result)
        self.assertAlmostEqual(result['destination_coordinates'][0], 37.82479, 2)
        self.assertAlmostEqual(result['destination_coordinates'][1],  -88.98, 2)


if __name__ == '__main__':
    unittest.main()
