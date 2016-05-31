from qgis.core import *
import qgis.utils
import ipdb
import datetime
import urllib2
import numpy as np
import matplotlib
matplotlib.use('Agg') # Workaround for Tkinter import error
import matplotlib.pyplot as plt
import json
import sys
import collections
import math

'''
This code's goal is to create an accurate model of biking traffic from Strava
data, both for differential measurements and absolute measurements calibrated
by some other independent, accurate measurement of biking. 

Strava differential measurements:

Assumes general population or at least trends are well described by Strava users

  1) Ridership by time of day
  2) Ridership by day of week
  3) Ridership by season
      - degeneracy between trends in Strava usage and trends in biking make
        this (and longer timescale analysis) suspect
  4) Ridership by weather
      - rain, snow, temperature, wind
  5) Ridership by location
      - can do for free with heatmap, qualitatively
  6) Ridership by age/gender
      - biased and ~uncorrectable

Strava absolute calibration:

Strava is marketed toward "hardcore" athletes and competitors -- not daily
commuters. A smart phone with a data plan (or similar, expensive, luxury,
techy gadget) is required. This likely biases the Strava data toward more
extreme behavior -- relatively higher usage in bad weather, on trails, on hills,
and also among more affluent, likely younger and male bikers. The popularity
of Strava, and the interest of its users to log their rides may wax and wane,
confusing efforts. The magnitude of these biases are likely regional, hyper
local, and condition dependent, but can be corrected for with independent,
calibrating data.

Potential confounding variables
  1) Weather
  2) Location
      - location type
          - trails, roads, rural, urban
      - radius of applicability
          - trends in Europe are not the same as US
              - and likely more local (distance from bike path?)
  3) Linear Time
      - increased/decreased strava usage
      - logging habits
  4) Time of day
      - Recreational hours vs commuting hours
  5) Time of year
  6) Grade
  7) Age
      - difficult to correct
  8) Gender
      - hard to correct
          - automated bike counters cannot differentiate
          - even manual bike counts are error prone


The quality of the calibration will depend critically on the spatial and temporal
frequency of bike counts to calibrate the data and the applicability of the model.
We do not require uniform, annual, or simultaneous bike counts. Any data point at
any time can be used to anchor the Strava data. The more varied the conditions,
the more accurate it will be. Can we set up a year round submission of bike count
data? Need to vet data. Install some of these?
http://bikeportland.org/2015/01/13/50-device-change-bike-planning-forever-130891
They would make excellent anchor points, particularly to calibrate the changes
in Strava user behavior over time.

Advantages to accurate ridership statistics
  1) determine what infrastructure improvements are most effective
  2) immediately measure the effacacy of infrastructure improvements
      - At least in terms of ridership
  3) determine if an accident is indicative of a dangerous intersection
      - Or is accident rate consistent with ridership rates?
  4) Determine where bike counts would be most effective

Other issues:
  1) Correlated errors
      - lots of data from one user could skew error estimates
      - non-Poisson distribution of bikers
          - bikers in groups
  2) Low number statistics
      - How many Strava users?
  3) Errors in bike counts

See here for a python cookbook for pyqgis:
http://spatialgalaxy.net/2014/10/09/a-quick-guide-to-getting-started-with-pyqgis-on-windows/
https://trac.osgeo.org/osgeo4w/
http://docs.qgis.org/testing/en/docs/pyqgis_developer_cookbook/raster.html

'''

# get the weather for a given day by airport code (is it international?)
def getWeather(date, airport='BOS', timezone=5):

    # https://www.wunderground.com/history/airport/BOS/2015/10/8/DailyHistory.html?&format=1
    url = 'https://www.wunderground.com/history/airport/' + airport + '/' +\
          str(date.year) + '/' + str(date.month) + '/' + str(date.day) +\
          '/DailyHistory.html?&format=1'
    request = urllib2.Request(url)
    try:
        response = urllib2.urlopen(request)
    except:
        print 'could not open ' + url
        return -1

    data = response.read().split('<br />\n')

    # is it stable? is it uniform for all airports/times? 
    # TODO: read with CSV reader (?), check that required keys are present
    weather = {'time':[],'temperature':[],'dewPoint':[],'humidity':[],'pressure':[],'visibility':[],
                'windDir':[],'windSpeed':[],'windGust':[],'precipitation':[],'events':[],'conditions':[]}    
    for values in data[1:]:
        valarr = values.split(',')
        if len(valarr) == 14:
            weather['time'].append(datetime.datetime.strptime(valarr[13],'%Y-%m-%d %H:%M:%S') -
                                   datetime.timedelta(hours=timezone))
            weather['temperature'].append(valarr[1])
            weather['dewPoint'].append(valarr[2])
            weather['humidity'].append(valarr[3])
            weather['pressure'].append(valarr[4])
            weather['visibility'].append(valarr[5])
            weather['windDir'].append(valarr[12])
            weather['windSpeed'].append(valarr[7])
            weather['windGust'].append(valarr[8])
            weather['precipitation'].append(valarr[9])
            weather['events'].append(valarr[10])
            weather['conditions'].append(valarr[11])
    return weather   

# get the field names of a given layer:
def getFieldNames(layer):
    field_names = [field.name() for field in layer.pendingFields()]
    return field_names

def getMinDist(x1,y1,x2,y2,x0,y0):

    if x2 == x1:
        # horizontal segment
        x = x1
        y = y0
    elif y1==y2:
        # vertical segment
        x = x0
        y = y1
    else:
        # the equation of the edge's line
        m1 = (y2-y1)/(x2-x1)
        b1 = y1 - m1*x1

        # the equation of the perpendicular line that passes through the specified point
        m2 = -1.0/m1
        b2 = y0 - m2*x0

        # the coordinates of intersection
        x = (b2-b1)/(m1-m2)
        y = m1*x+b1

    # must be closest to the segment, not the line
    if x1 > x2: # can't assume x1 < x2
        if x > x1: x = x1
        if x < x2: x = x2
    else:
        if x < x1: x = x1
        if x > x2: x = x2
    if y1 > y2: # can't assume y1 < y2
        if y > y1: y = y1
        if y < y2: y = y2
    else:
        if y < y1: y = y1
        if y > y2: y = y2

    # closest approach is the distance from the perpendicular line
    # angular separation in radians * r_earth = distance
    r_earth = 6.3781e6
    mindist = math.acos(math.sin(y0*math.pi/180.0)*math.sin(y*math.pi/180.0)+math.cos(y0*math.pi/180.0)*math.cos(y*math.pi/180.0)*math.cos((x0-x)*math.pi/180.0))*r_earth

    return mindist

def plotEdges(edge_layer,lat=None,lon=None,radius=None, edgeids=[]):

    # edge file is in this coordinate system
    # +proj=longlat +datum=WGS84 +no_defs

    crs = QgsCoordinateReferenceSystem(4326, QgsCoordinateReferenceSystem.PostgisCrsId)
    crsSrc = QgsCoordinateReferenceSystem(4326)    # WGS 84
    crsDest = QgsCoordinateReferenceSystem(32633)  # WGS 84 / UTM zone 33N
    xform = QgsCoordinateTransform(crsSrc, crsDest)

# forward transformation: src -> dest
#pt1 = xform.transform(QgsPoint(40,-70))
#print "Transformed point:", pt1

# inverse transformation: dest -> src
#pt2 = xform.transform(pt1, QgsCoordinateTransform.ReverseTransform)
#print "Transformed back:", pt2

    x = [] # Longitude (deg E)
    y = [] # Latitude (deg N)

    xclose = []
    yclose = []
    streetname = []
    
    idxx1 = edge_layer.fieldNameIndex('X1') 
    idxx2 = edge_layer.fieldNameIndex('X2') 
    idxy1 = edge_layer.fieldNameIndex('Y1') 
    idxy2 = edge_layer.fieldNameIndex('Y2')

    for feature in edge_layer.getFeatures():
        pt1 = xform.transform(QgsPoint(feature[idxx1],feature[idxy1]))
        pt2 = xform.transform(QgsPoint(feature[idxx2],feature[idxy2]))

#        x.append(-pt1[1])
#        x.append(-pt2[1])
        x.append(feature[idxx1]*math.cos(feature[idxy1]*math.pi/180.0))
        x.append(feature[idxx2]*math.cos(feature[idxy2]*math.pi/180.0))
        x.append(None)
#        y.append(pt1[0])
#        y.append(pt2[0])
        y.append(feature[idxy1])#/math.cos(feature[idxx1]*math.pi/180.0))
        y.append(feature[idxy2])#/math.cos(feature[idxx2]*math.pi/180.0))
        y.append(None)

        
        
        if lat != None and lon != None:
            if radius != None:
                mindist = getMinDist(feature[idxx1],feature[idxy1],feature[idxx2],feature[idxy2],lon,lat)
                if mindist <= radius:
                    xclose.append(feature[idxx1])
                    xclose.append(feature[idxx2])
                    xclose.append(None)
                    yclose.append(feature[idxy1])
                    yclose.append(feature[idxy2])
                    yclose.append(None)
                    edgeid = feature[0]
                    streetname = feature[2]
        if feature[0] in edgeids:
            xclose.append(feature[idxx1])
            xclose.append(feature[idxx2])
            xclose.append(None)
            yclose.append(feature[idxy1])
            yclose.append(feature[idxy2])
            yclose.append(None)
            streetname.append(feature[2])
            

#    lon = xclose[0]
#    lat = yclose[0]
    lon = -97.67
    lat = 40.77
    fig = plt.figure()
    ax = fig.add_subplot(111)
    ax.set_xlabel("Longitude (deg E)")
    ax.set_ylabel("Latitude (deg N)")

    y_formatter = matplotlib.ticker.ScalarFormatter(useOffset=False)
    ax.yaxis.set_major_formatter(y_formatter)
    ax.xaxis.set_major_formatter(y_formatter)
    size = 0.1
#    ax.set_ylim([lat-size,lat+size])
#    ax.set_xlim([lon-size,lon+size])
    
    plt.plot(x, y)
    plt.plot(xclose, yclose, 'r-')
#    plt.plot(lon,lat,'ro')
#    ax.annotate('E 79th St @ Park Ave (' + str(edgeid) + ')',xy=(lon+0.0001,lat))
#    ax.annotate(streetname + '(' + str(edgeid) + ')',xy=(lon+0.0001,lat))
    plt.savefig('edge.png')

# supply path to qgis install location
QgsApplication.setPrefixPath("C:/OSGeo4W64", True)

# create a reference to the QgsApplication, setting the
# second argument to False disables the GUI
#qgs = QgsApplication([], False)
qgs = QgsApplication([], True)

# load providers
qgs.initQgis()

# Write your code here to load some layers, use processing algorithms, etc.
edge_layer = QgsVectorLayer("data/nyc_edges_ride/nyc_edges.shp", "NYC_Edges", "ogr")
if not edge_layer.isValid():
  print "edge layer failed to load!"
else: QgsMapLayerRegistry.instance().addMapLayer(edge_layer)

node_layer = QgsVectorLayer("data/nyc_edges_ride/nyc_edges_nodes.shp", "NYC_Nodes", "ogr")
if not node_layer.isValid():
  print "node layer failed to load!"
else: QgsMapLayerRegistry.instance().addMapLayer(node_layer)

poly_layer = QgsVectorLayer("data/nyc_edges_ride/nyc_edges_od_polygons.shp", "NYC_Polygons", "ogr")
if not poly_layer.isValid():
  print "polygon layer failed to load!"
else: QgsMapLayerRegistry.instance().addMapLayer(poly_layer)  

data_layer = QgsVectorLayer("data/nyc_edges_ride/nyc_edges_metro_street_data.dbf", "NYC_Data", "ogr")
if not data_layer.isValid():
  print "data layer failed to load!"
else: QgsMapLayerRegistry.instance().addMapLayer(data_layer)  

plotEdges(edge_layer)


'''
crs = QgsCoordinateReferenceSystem(4326, QgsCoordinateReferenceSystem.PostgisCrsId)
crsSrc = QgsCoordinateReferenceSystem(4326)    # WGS 84
crsDest = QgsCoordinateReferenceSystem(32633)  # WGS 84 / UTM zone 33N
xform = QgsCoordinateTransform(crsSrc, crsDest)

# forward transformation: src -> dest
pt1 = xform.transform(QgsPoint(40,-70))
print "Transformed point:", pt1

# inverse transformation: dest -> src
pt2 = xform.transform(pt1, QgsCoordinateTransform.ReverseTransform)
print "Transformed back:", pt2



ipdb.set_trace()
    
                    
crs = QgsCoordinateReferenceSystem(4326, QgsCoordinateReferenceSystem.PostgisCrsId)
'''    


#print getFieldNames(data_layer)
#print getFieldNames(edge_layer)

# E 79th & Park Ave
lat = 40.775578
lon = -73.960339

# Manhattan Bridge Bikepath
#lat = 40.714629
#lon = -73.994544

#plotEdges(edge_layer, edgeid=1134166)# lat=lat, lon=lon, radius=2.5)
#plotEdges(edge_layer, edgeid=803175)
#plotEdges(edge_layer, edgeid=54068)
#plotEdges(edge_layer, lat=lat, lon=lon, radius=2.5)
plotEdges(edge_layer, edgeids=[1134166,803175,54068,54853])# lat=lat, lon=lon, radius=2.5)

with open('weather.lga.csv','w') as weatherfile:
    for i in range(8):
        weather = getWeather(datetime.datetime(2015,7,13) + datetime.timedelta(days=float(i)),airport='LGA')
#    ipdb.set_trace()
        for time, temperature, humidity, precipitation in zip(weather['time'],weather['temperature'],weather['humidity'],weather['precipitation']):
                if precipitation == 'N/A': precipitation = 0.0
                weatherfile.write(str(time) + ',' + str(temperature) + ',' + str(humidity) + ',' + str(precipitation) + '\n')
#ipdb.set_trace()
    

# grab the indices of relevant fields
idxYear = data_layer.fieldNameIndex('YEAR')
idxDay = data_layer.fieldNameIndex('DAY')
idxHour = data_layer.fieldNameIndex('HOUR')
idxMin = data_layer.fieldNameIndex('MINUTE')
idxCommuters = data_layer.fieldNameIndex('COMMUTE_CO')
idxEdge = data_layer.fieldNameIndex('EDGE_ID')
idxx1 = edge_layer.fieldNameIndex('X1') 
idxx2 = edge_layer.fieldNameIndex('X2') 
idxy1 = edge_layer.fieldNameIndex('Y1') 
idxy2 = edge_layer.fieldNameIndex('Y2')

# index the edges by edge ID
print "Creating the edge ID indices"
edges = {}
for feature in edge_layer.getFeatures():
    edges[feature[0]] = {'x':[feature[idxx1],feature[idxx2]],
                         'y':[feature[idxy1],feature[idxy2]]}

# index the data layer by date
print "Creating the date indices"

commutersmin = {}
commutershr = {}
commuters15min = {}
for i in range(0,24*7*60):
    date = datetime.datetime(2015,7,13) + datetime.timedelta(minutes=float(i))
    commutersmin[str(date)] = []

    if date.minute == 0:
        commuters15min[str(date)] = []
        commutershr[str(date)] = []

    if date.minute == 15 or date.minute == 30 or date.minute == 45:
        commuters15min[str(date)] = []

for feature in data_layer.getFeatures():
    datemin = datetime.datetime(feature[idxYear],1,1,feature[idxHour],feature[idxMin]) +\
              datetime.timedelta(days=feature[idxDay]-1)

    if datemin >= datetime.datetime(2015,7,13) and datemin < datetime.datetime(2015,7,20):
        datehr = datetime.datetime(feature[idxYear],1,1,feature[idxHour]) +\
                 datetime.timedelta(days=feature[idxDay]-1)


        if feature[idxMin] < 15: minute = 0
        elif feature[idxMin] < 30: minute = 15
        elif feature[idxMin] < 45: minute = 30
        else: minute = 45
        date15min = datetime.datetime(feature[idxYear],1,1,feature[idxHour], minute) +\
                    datetime.timedelta(days=feature[idxDay]-1)

        commutersmin[str(datemin)].append(feature)
        commutershr[str(datehr)].append(feature)
        commuters15min[str(date15min)].append(feature)

print "Done making data indices"

# make an animated gif of bicycle traffic
#for i in range(0,24*7):
for i in range(0,24*7*60):
    date = datetime.datetime(2015,7,13) + datetime.timedelta(minutes=float(i))

    fig = plt.figure()
    ax = fig.add_subplot(111, aspect='equal')
    ax.set_xlabel("Longitude (deg E)")
    ax.set_ylabel("Latitude (deg N)")
    ax.set_title(str(date))
    y_formatter = matplotlib.ticker.ScalarFormatter(useOffset=False)
    ax.yaxis.set_major_formatter(y_formatter)
    ax.xaxis.set_major_formatter(y_formatter)
    ax.set_ylim([40.67,40.90])
    ax.set_xlim([-74.03,-73.90])
    ax.set_xticks([-74,-73.95,-73.9])
    for feature in commutersmin[str(date)]:
        edgeid = feature[idxEdge]
        x = edges[edgeid]['x']
        y = edges[edgeid]['y']
        alpha = min([float(feature[idxCommuters])*0.3,1])
        plt.plot(x, y, 'b-', alpha=alpha)

    plt.savefig("minutegif/" + datetime.datetime.strftime(date,'%Y-%m-%dT%H%M%S') + '.png') 
    plt.close()
    
ipdb.set_trace()
commuters = collections.OrderedDict()
i=0
bad = 0
for i in range(24*7):
    date = datetime.datetime(2015,7,13) + datetime.timedelta(hours=float(i))
    commuters[str(date)] = 0

for feature in data_layer.getFeatures():
    # convert strava time (local time) to datetime object 
    date = datetime.datetime(feature[idxYear],1,1,feature[idxHour],feature[idxMin]) +\
           datetime.timedelta(days=feature[idxDay]-1)

    datestr = str(datetime.datetime(feature[idxYear],1,1,feature[idxHour]) +\
           datetime.timedelta(days=feature[idxDay]-1))

    # filter out dates that aren't supposed to be in the sample (not complete)
    if date >= datetime.datetime(2015,7,20): bad += 1
    else:
#        if feature[idxEdge] == 1134166: # Manhattan Bridge Bikepath
#        if feature[idxEdge] == 54853: # Random spot
#        if feature[idxEdge] == 803175: # spot with 43 total weekly commuters; roughly scales to busiest by total population
        if feature[idxEdge] == 54068: # spot with 122 total weekly commuters; roughly scales to busiest by population density
            commuters[datestr] += feature[idxCommuters]
        
#    print feature[idxEdge], date, feature[idxCommuters]
#    if str(date) in commuters.keys(): commuters[str(date)] += feature[idxCommuters]
#    else: commuters[str(date)] = feature[idxCommuters]

    # print progress
    i += 1
    if i % 10000 == 0: print float(i)#/float(nfeatures)

with open('commuters.hour.4@E14.csv','w') as commuterfile:
    for key in commuters.keys():
        commuterfile.write(key + ',' + str(commuters[key]) + '\n')

ipdb.set_trace()

edgeCommuters = collections.OrderedDict()
for feature in edge_layer.getFeatures():
    edgeCommuters[feature[0]] = 0

for feature in data_layer.getFeatures():
    edgeCommuters[feature[0]] += feature[idxCommuters]

with open('edgecommuters.csv','w') as commuterfile:
    for key in edgeCommuters.keys():
        commuterfile.write(str(key) + ',' + str(edgeCommuters[key]) + '\n')


#weather = getWeather(datetime.datetime(2015,7,13), airport='JFK')
#print bad
ipdb.set_trace()

# When your script is complete, call exitQgis() to remove the provider and
# layer registries from memory
qgs.exitQgis()

    
