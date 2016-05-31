import matplotlib
matplotlib.use('Agg') # Workaround for Tkinter import error
import matplotlib.pyplot as plt
import json
import csv
import datetime
import ipdb
from qgis.core import *

with open('x.dat') as xfile:
    x = json.load(xfile)
with open('y.dat') as yfile:
    y = json.load(yfile)

fig = plt.figure()

ax = fig.add_subplot(111, aspect='equal')
ax.set_xlabel("Longitude (deg E)")
ax.set_ylabel("Latitude (deg N)")

y_formatter = matplotlib.ticker.ScalarFormatter(useOffset=False)
ax.yaxis.set_major_formatter(y_formatter)
ax.xaxis.set_major_formatter(y_formatter)
ax.set_ylim([40.67,40.90])
ax.set_xlim([-74.03,-73.90])
ax.set_xticks([-74,-73.95,-73.9])

plt.plot(x,y)
plt.savefig('edge.png')
plt.show()

ipdb.set_trace()

fig = plt.figure()
ax=fig.add_subplot(111)
ax.set_xlabel("Time (ET)")
#fig.suptitle('NYC Sample Data')
ax.set_title("New York County Sample Strava Data")
ax.set_xlim([datetime.datetime(2015,7,13),datetime.datetime(2015,7,20)])

time = []
commuters = []
with open('commuters.hour.csv','rb') as csvfile:
    reader = csv.reader(csvfile)
    for row in reader:
        time.append(datetime.datetime.strptime(row[0],'%Y-%m-%d %H:%M:%S'))
        commuters.append(float(row[1])/360.0)

plt.plot(time,commuters,label="Strava commuters/10 seconds")

time = []
temp = []
precipitation = []
humidity = []
with open('weather.lga.csv','rb') as csvfile:
    reader = csv.reader(csvfile)
    for row in reader:
        time.append(datetime.datetime.strptime(row[0],'%Y-%m-%d %H:%M:%S'))
        temp.append(row[1])
        humidity.append(row[2])
        precipitation.append(float(row[3])*100)

plt.plot(time, temp, label='Temperature (F)',alpha=0.25)
plt.plot(time, precipitation, label='Precipitation (0.01")',alpha=0.25)
plt.plot(time, humidity, label='Humidity (%)',alpha=0.25)


#handles, labels = plt.get_legend_handles_labels()
plt.legend()

#plt.legend([a,b,c,d])
plt.savefig('commuters.png')
plt.show()
