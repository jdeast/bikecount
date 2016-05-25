import matplotlib.pyplot as plt
import json
import csv
import datetime
import ipdb

with open('x.dat') as xfile:
    x = json.load(xfile)
with open('y.dat') as yfile:
    y = json.load(yfile)

plt.plot(x,y)
plt.savefig('edge.png')
plt.show()

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
