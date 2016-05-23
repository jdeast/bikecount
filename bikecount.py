from qgis.core import *
import qgis.utils
#import ipdb
import datetime
import urllib2
import numpy as np
import matplotlib
#matplotlib.use('Agg',warn=False)
import matplotlib.pyplot as plt

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

def plotEdges(edge_layer):
    x = []
    y = []
    idxx1 = edge_layer.fieldNameIndex('X1')
    idxx2 = edge_layer.fieldNameIndex('X2')
    idxy1 = edge_layer.fieldNameIndex('Y1')
    idxy2 = edge_layer.fieldNameIndex('Y2')

    for feature in edge_layer.getFeatures():
        x.append(feature[idxx1])
        x.append(feature[idxx2])
        x.append(None)
        y.append(feature[idxy1])
        y.append(feature[idxy2])
        y.append(None)

    fig = plt.figure()
#    ax = fig.add_subplot(121)
    plt.plot(x, y)
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

print getFieldNames(data_layer)

# grab the indices of relevant fields
idxYear = data_layer.fieldNameIndex('YEAR')
idxDay = data_layer.fieldNameIndex('DAY')
idxHour = data_layer.fieldNameIndex('HOUR')
idxMin = data_layer.fieldNameIndex('MINUTE')
idxCommuters = data_layer.fieldNameIndex('COMMUTE_CO')
idxEdge = data_layer.fieldNameIndex('EDGE_ID')



plotEdges(edge_layer)

sys.exit()
#ipdb.set_trace()

#ipdb.set_trace()
commuters = {}
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
    else: commuters[datestr] += feature[idxCommuters]
        
#    print feature[idxEdge], date, feature[idxCommuters]
#    if str(date) in commuters.keys(): commuters[str(date)] += feature[idxCommuters]
#    else: commuters[str(date)] = feature[idxCommuters]

    # print progress
    i += 1
    if i % 10000 == 0: print float(i)#/float(nfeatures)

    

#weather = getWeather(datetime.datetime(2015,7,13), airport='JFK')
print bad
#ipdb.set_trace()

# When your script is complete, call exitQgis() to remove the provider and
# layer registries from memory
qgs.exitQgis()

    
