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
import urllib2
import matplotlib.dates as mdates
import csv
import numpy as np
import emcee
import corner

def updateData():
    key = "1uZ4_bSXdB188mBj8PVJL4fGErOeOyN1g5OR8_ZLdAlk"
    gid = "1919569404"
    response = urllib2.urlopen("https://docs.google.com/spreadsheet/ccc?key=" + key + "&output=csv", timeout = 5)
    countdata = response.read().split('\r\n')
    response = urllib2.urlopen("https://docs.google.com/spreadsheet/ccc?key=" + key + "&gid=" + gid + "&output=csv", timeout = 5)
    locationdata = response.read().split('\r\n')
    f = open( "count.csv", 'w' )
    f.write( '\n'.join(countdata))
    f.close()
    f = open( "location.csv", 'w' )
    f.write( '\n'.join(locationdata))
    f.close()

def readcsv(csvname):
    # read the CSV file into a dictionary
    f = open(csvname, 'rb')
    reader = csv.reader(f)
    headers = reader.next()
    values = {}
    for h in headers:
        values[h] = []
    for row in reader:
        for h, v in zip(headers, row):
            values[h].append(v)    
    return values


# get the weather for a given day by airport code (is it international?)
#def getWeather(date, airport='BOS', timezone=5):
def getWeather(date, airport='BED', timezone=5):

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

# calculate the likelihood of a given set of parameters given the data
def bikelike(pars, data, bikers=None, plot=False):

    # Bike count model:
    # bikers(location,time) = zeropoint(location)*(c0*temperature(time) + c1*humidity(time) + c2*rain(time))
    # pars[0] = coeff_temp
    # pars[1] = coeff_humidity
    # pars[2] = coeff_rain
    # pars[3:] = zeropoints

    locations = list(set(data['Location']))
#    if len(locations)+3 != len(pars):
    if len(locations)+2 != len(pars):
        print "Parameter array does not match data; exiting"
        sys.exit()

    locations.sort()
    nlocations = len(locations)
    bikers = np.zeros(len(data['Location']))
    residuals = np.zeros(len(data['Location']))

    for i in range(nlocations):        
        match = np.where(data['Location'] == locations[i])
#        bikers[match] = pars[i+3]*(pars[0]*data['Temperature (BED)'][match] + pars[1]*data['Humidity (BED)'][match] + pars[2]*data['Precipitation (BED)'][match])
        bikers[match] = pars[i+2]*(pars[0]*data['Temperature (BED)'][match] + pars[1]*data['Humidity (BED)'][match])
#        bikers[match] = pars[i+2]*(pars[0]*data['Temperature (BED)'][match] + pars[1]*data['Precipitation (BED)'][match])

        if plot:
            fig = plt.figure()
            ax = fig.add_subplot(111)
            ax.set_xlabel("Date")
            ax.set_ylabel("Bikers/minute")
            ax.set_title(locations[i])
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y'))
            ax.xaxis.set_ticks([datetime.datetime(2013,1,1),datetime.datetime(2014,1,1),datetime.datetime(2015,1,1),datetime.datetime(2016,1,1)])
            ax.set_xlim([datetime.datetime(2013,1,1),datetime.datetime(2017,1,1)])
            y_formatter = matplotlib.ticker.ScalarFormatter(useOffset=False)
            ax.yaxis.set_major_formatter(y_formatter)

            # data corrected to 70F, 0% humid, 0" rain
#            y = pars[i+3]*pars[0]*(70-data['Temperature (BED)'][match]) +\
#                bikers[match] - data['Total Bike'][match]/data['Interval'][match]
            y = pars[i+2]*pars[0]*(70-data['Temperature (BED)'][match]) +\
                bikers[match] - data['Total Bike'][match]/data['Interval'][match]
#            print y
          
            plt.plot(data['datetime'][match].astype(datetime.datetime), y, 'bo', label=locations[i])
#            plt.plot(data['datetime'][match].astype(datetime.datetime), bikers[match], 'bo', label=locations[i])
#            plt.plot(data['datetime'][match].astype(datetime.datetime), data['Total Bike'][match]/data['Interval'][match], 'ro', label=locations[i])

            plt.savefig(locations[i] + '.png')
            plt.close()
#            ipdb.set_trace()
            

    # negative bikers is unphysical
    bad = np.where(bikers < 0)
    if len(bad[0] > 0): return np.NINF
    
    residuals = bikers - data['Total Bike']/data['Interval']

    # Poisson Errors
#    sigma = sqrt(bikers)/data['Interval']
#    ivar = (1.0/sigma)**2
    ivar = data['Interval']**2/bikers

    loglike = -0.5*np.sum(ivar*residuals**2)
#    if loglike > -20: ipdb.set_trace()

    if math.isnan(loglike): ipdb.set_trace()
    
    return -0.5*np.sum(ivar*residuals**2)

# read the CSV file into a dictionary
data = readcsv('count.csv')

# convert date and time to datetime objects
data['datetime'] = np.array([],dtype=np.datetime64)
for date,time in zip(data['Date'],data['Time']):
    data['datetime'] = np.append(data['datetime'], np.datetime64(datetime.datetime.strptime(date + ' ' + time,'%m/%d/%Y %H:%M')))

# define and convert the data types to numpy arrays
datatypes = {
    'Location':str,
    'Weather':str,
    'Counter':str,
    'Notes':str,
    'Latitude':float,
    'Longitude':float,
    'Female Ped':float,
    'Male Ped':float,
    'Total Ped':float,
    'Female Bike':float,
    'Male Bike':float,
    'Total Bike':float,
    'Female Other':float,
    'Male Other':float,
    'Total Other':float,
    'Interval':float,
    'Precipitation (BED)':float,
    'Temperature (BED)':float,
    'Humidity (BED)':float,
    }
for key in datatypes.keys():
    array=[]
    for value in data[key]:
        if value=='':
            value = np.nan
        array.append(value)
    data[key] = np.asarray(array,dtype=datatypes[key])

# The unique locations
locations = list(set(data['Location']))
locations.sort()


#ndim, nwalkers = len(locations)+3, 100
ndim, nwalkers = len(locations)+2, 1000
sampler = emcee.EnsembleSampler(nwalkers, ndim, bikelike, args=[data])

initpars = [0.0,0.0]
for location in locations:
    match = np.where(data['Location'] == location)
    zeropt = np.sum(data['Total Bike'][match])/np.sum(data['Interval'][match])
    initpars.append(zeropt)
print initpars


p0 = [np.random.rand(ndim)/1000 + initpars for i in range(nwalkers)]


sampler.run_mcmc(p0, 10000)

#labels = ['coeff_temp','coeff_humid','coeff_rain']
labels = ['coeff_temp','coeff_humid']
for location in locations:
    labels.append("c_" + location)

samples = sampler.chain[:, 50:, :].reshape((-1, ndim))
for i in range(ndim):
    plt.figure()
    plt.hist(samples[:,i], 100, color="k", histtype="step")
    plt.title(labels[i])
    plt.savefig("Dimension{0:d}".format(i) + '.png')
    plt.close()

#ipdb.set_trace()

maxlike = np.NINF

for i in range(len(locations)):
    '''
    fig = plt.figure()
    ax = fig.add_subplot(111)
    ax.set_xlabel("Date")
    ax.set_ylabel("Bikers/minute")
    ax.set_title(locations[i])
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y'))
    ax.xaxis.set_ticks([datetime.datetime(2013,1,1),datetime.datetime(2014,1,1),datetime.datetime(2015,1,1),datetime.datetime(2016,1,1)])
    ax.set_xlim([datetime.datetime(2013,1,1),datetime.datetime(2017,1,1)])
    y_formatter = matplotlib.ticker.ScalarFormatter(useOffset=False)
    ax.yaxis.set_major_formatter(y_formatter)
    '''
    
    match = np.where(data['Location'] == locations[i])

    x = data['datetime'][match].astype(datetime.datetime)
    for pars in samples[np.random.randint(len(samples), size=1000)]:
        like = bikelike(pars,data)
        print like, pars[0:2]
        if like > maxlike:
            maxlike = like
            bestpars = pars

        bikers = pars[i+2]*(pars[0]*data['Temperature (BED)'][match] + pars[1]*data['Humidity (BED)'][match])
        #plt.plot(x, bikers, 'b-', label=location, alpha=0.01)

    y = data['Total Bike'][match]/data['Interval'][match]
#    plt.plot(x, y, 'bo', label=location)


#    plt.savefig(locations[i] + '.png')
#    plt.close()
    

#ipdb.set_trace()
print bestpars
bikelike(bestpars,data,plot=True)
ipdb.set_trace()


# make a triangle plot
fig = corner.corner(samples, labels=labels)
fig.savefig("triangle.png")


ipdb.set_trace()


#from matplotlib.font_manager import FontProperties
#fontP = FontProperties()
#fontP.set_size('small')
zeropoints = np.zeros((len(locations),len(data['datetime'])),dtype=float)

i=0
for location in locations:

    fig = plt.figure()
    ax = fig.add_subplot(111)
    ax.set_xlabel("Date")
    ax.set_ylabel("Bikers/minute")
    ax.set_title(location)
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y'))
    ax.xaxis.set_ticks([datetime.datetime(2013,1,1),datetime.datetime(2014,1,1),datetime.datetime(2015,1,1),datetime.datetime(2016,1,1)])
    ax.set_xlim([datetime.datetime(2013,1,1),datetime.datetime(2017,1,1)])
    y_formatter = matplotlib.ticker.ScalarFormatter(useOffset=False)
    ax.yaxis.set_major_formatter(y_formatter)

    match = np.where(data['Location'] == location)

    zeropoints[i][match] = 1.0

    pars1 = [2.98955584e-3,-1.93944467e-4,-1.96151944] # fitting just temp, humid, rain
    pars1 = [0.00293953,-0.00151096,0.9622594] # fitting temp, humid, rain, and zeropoints for each location
    pars1 = [0.00381207,-0.00133282] # fitting temp, humid, zeropoints

    y = data['Total Bike'][match]/data['Interval'][match] +\
        (70-data['Temperature (BED)'][match])*pars1[0] +\
        (0-data['Humidity (BED)'][match])*pars1[1] #+\
#        (0-data['Precipitation (BED)'][match])*pars1[2] 
    
  
    plt.plot(data['datetime'][match].astype(datetime.datetime), y, 'bo', label=location)
#    print data['datetime'][match], data['Total Bike'][match]/data['Interval'][match], location

    plt.savefig(location + '.png')
    plt.close()

    i += 1

fig = plt.figure()
ax = fig.add_subplot(111)
ax.set_xlabel("Temperature (BED)")
ax.set_ylabel("Bikers/minute")
y_formatter = matplotlib.ticker.ScalarFormatter(useOffset=False)
ax.yaxis.set_major_formatter(y_formatter)
plt.plot(data['Temperature (BED)'],data['Total Bike']/data['Interval'],'bo')
plt.savefig('countvtemp.png')
plt.close()

fig = plt.figure()
ax = fig.add_subplot(111)
ax.set_xlabel("Humidity (BED)")
ax.set_ylabel("Bikers/minute")
y_formatter = matplotlib.ticker.ScalarFormatter(useOffset=False)
ax.yaxis.set_major_formatter(y_formatter)
plt.plot(data['Humidity (BED)'],data['Total Bike']/data['Interval'],'bo')
plt.savefig('countvhumidity.png')
plt.close()

fig = plt.figure()
ax = fig.add_subplot(111)
ax.set_xlabel("Precipitation (BED)")
ax.set_ylabel("Bikers/minute")
y_formatter = matplotlib.ticker.ScalarFormatter(useOffset=False)
ax.yaxis.set_major_formatter(y_formatter)
plt.plot(data['Precipitation (BED)'],data['Total Bike']/data['Interval'],'bo')
plt.savefig('countvrain.png')
plt.close()





temp = data['Temperature (BED)']
humid = data['Humidity (BED)']
rain = data['Precipitation (BED)']
time = data['datetime']



A = np.vstack([temp, humid, rain, zeropoints]).T

A = np.vstack([temp, humid, zeropoints]).T
#lt alt,az,cosrot,sinrot,temp,np.ones(len(x))]).T

y = data['Total Bike']/data['Interval']
pars = np.linalg.lstsq(A,y)[0]

model = np.dot(A,pars)



residuals = y-model


npars = 2
nxplots = 1
nyplots = npars
fig = plt.figure(figsize=(15, 12))
ax = fig.add_subplot(nyplots,nxplots,1)

labels = ['Temperature', 'Humidity','Rain']
for location in locations: labels.append(location)
           
for i in range(npars):

    ax = fig.add_subplot(nyplots,nxplots,i)
    sub = residuals + pars[i]*A[:,i]
    ax.scatter(A[:,i], sub)
    ax.plot(A[:,i], pars[i]*A[:,i],color='r')
    ax.set_xlabel(labels[i])
    ax.set_ylabel("Bikes/minute")

fig.savefig("corrected_count.png")
print pars
ipdb.set_trace()               
#plt.legend(prop=fontP)

#legend([plot1], "title", prop = fontP)

    
