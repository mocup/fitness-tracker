# By Morgan Cupp (mmc274) and Maanav Shah (mcs356)
# ECE 5725 Final Project: Fitness Tracker
# Completed: May 9, 2022

import time
import RPi.GPIO as GPIO
import pygame
from pygame.locals import *
import os
import adafruit_gps
import serial
from geopy import distance
import datetime
import matplotlib
import matplotlib.pyplot as plt
import numpy as np

# configure GPIO
GPIO.setmode(GPIO.BCM) # set broadcom
GPIO.setup(27, GPIO.IN, pull_up_down=GPIO.PUD_UP) # quit button

# piTFT setup
os.putenv('SDL_VIDEODRIVER', 'fbcon') # display on piTFT
os.putenv('SDL_FBDEV', '/dev/fb0') # use this when HDMI is not plugged in
os.putenv('SDL_MOUSEDRV', 'TSLIB') # track mouse clicks on piTFT
os.putenv('SDL_MOUSEDEV', '/dev/input/touchscreen')

pygame.init() # initialize pygame

# set up GPS module
uart = serial.Serial('/dev/ttyUSB0', baudrate=9600, timeout=10) # set up serial to GPS module
gps = adafruit_gps.GPS(uart, debug=False) # create GPS module instance
gps.send_command(b'PMTK314,0,1,0,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0') # enable GGA and RMC info
gps.send_command(b'PMTK220,1000') # update GPS once per second

# pygame configuration
pygame.mouse.set_visible(False) # false when running on piTFT
screen = pygame.display.set_mode((320,240)) # display size
large_font = pygame.font.Font(None, 80) # large font size
medium_font = pygame.font.Font(None, 50) # medium font size
small_font = pygame.font.Font(None, 30) # small font size
home_button_size = 60, 60
button_size = 40,40

# RGB color representations
WHITE = 255, 255, 255
BLACK = 0,0,0
RED = 255, 0, 0
GREEN = 0, 255, 0

# global variables
last_time = time.monotonic() # last time gps was updated
labels = {'distance': (53,15), 'time': (159,15), 'speed': (265,15), # labels for data fields
          'elevation gain': (100,100), 'altitude': (221,100)}
altitude = 0 # current altitude
elevation_gain = 0 # total elevation gain during an activity
first_val_alt = True # true when no altitude values have been measured yet
prev_altitude = 0 # previous altitude measured
speed = 0 # current speed
dist = 0 # accumulator used for distance travelled
prev_latitude = 0 # previous latitude measured
prev_longitude = 0 # previous longitude measured
first_val = True # true when no distance values have been measured yet
ref_time = 0 # reference time being used to measure activity duration
elapsed_time = '00:00:00' # elapsed time of the user's current activity
prev_time = 0 # previous time measured
screen_num = 0 # index of the screen being displayed (when using arrow buttons)
activities = [] # list of names of all activity files
summaries = [] # list of names of all activity summmary files
graphs = [] # list of names of all activity summmary files
graph_path = '' # path to the name of a particular graph file

# flags
code_running = True # run code while this is true
on_home_screen = True # true when when user is on the home screen
on_bike_screen = False # true when user is on bike screen
on_history_screen = False # true when user is on history screen
on_summary_screen = False # true when user is on summary screen
on_graph_screen = False # true when user is on graph screen
start = False # true when an activity has been started
pause = False # true when an activity is paused

screen.fill(BLACK) # erase workspace

# load images
bike = pygame.image.load('/home/pi/final_project/images/bike.jpg')
bike = pygame.transform.scale(bike, home_button_size)
history = pygame.image.load('/home/pi/final_project/images/history.png')
history = pygame.transform.scale(history, home_button_size)
left_arrow = pygame.image.load('/home/pi/final_project/images/left_arrow.png')
left_arrow = pygame.transform.scale(left_arrow, button_size)
right_arrow = pygame.image.load('/home/pi/final_project/images/right_arrow.png')
right_arrow = pygame.transform.scale(right_arrow, button_size)
home = pygame.image.load('/home/pi/final_project/images/home.png')
home = pygame.transform.scale(home, button_size)
summary = pygame.image.load('/home/pi/final_project/images/summary.png')
summary = pygame.transform.scale(summary, home_button_size)
dist_graph = pygame.image.load('/home/pi/final_project/images/distance.png')
dist_graph = pygame.transform.scale(dist_graph, button_size)
time_graph = pygame.image.load('/home/pi/final_project/images/time.png')
time_graph = pygame.transform.scale(time_graph, button_size)
elev_graph = pygame.image.load('/home/pi/final_project/images/elevation.png')
elev_graph = pygame.transform.scale(elev_graph, button_size)

# create home screen buttons
home_screen_buttons = {history: (60,190), bike: (160,190), summary: (260,190)}
home_screen_button_rects = {}

for image, position in home_screen_buttons.items():
    rect = image.get_rect(center=position)
    home_screen_button_rects[image] = rect

# create bike screen buttons
bike_screen_buttons = {'save': (107,200), 'start': (214,200), 'pause': (214,200), 'back': (30,200)}
bike_screen_button_rects = {}
    
for text, position in bike_screen_buttons.items():
    text_surface = small_font.render(text, True, WHITE)
    rect = text_surface.get_rect(center=position)
    bike_screen_button_rects[text] = rect
    
# create arrow buttons
arrow_buttons = {home: (60,220), left_arrow: (160,220), right_arrow: (260,220)}
arrow_button_rects = {}

for image, position in arrow_buttons.items():
    rect = image.get_rect(center=position)
    arrow_button_rects[image] = rect
    
# create graph selection buttons
graph_selection_buttons = {dist_graph: (60,170), time_graph: (160,170), elev_graph: (260,170)}
graph_selection_button_rects = {}

for image, position in graph_selection_buttons.items():
    rect = image.get_rect(center=position)
    graph_selection_button_rects[image] = rect

# display the time of day on the home screen
def display_time_of_day():
    global time_of_day
    
    if not gps.has_fix: # if GPS not connected, can't tell the time
        time_of_day = 'NO GPS'
    else:
        time_of_day = '{:02}:{:02}:{:02}'.format( # get UTC time from gps
                gps.timestamp_utc.tm_hour,
                gps.timestamp_utc.tm_min,
                gps.timestamp_utc.tm_sec,
            )
        hour = (int(time_of_day[:2])-4)%24 # convert UTC time to EST
        if (hour < 12): # convert 24-hour EST time to AM/PM
            am_pm = 'AM'
        elif (hour == 12):
            am_pm = 'PM'
        else:
            am_pm = 'PM'
            hour = hour-12
        time_of_day = str(hour) + time_of_day[2:] + ' ' + am_pm
    text_surface = large_font.render(time_of_day, True, WHITE)
    rect = text_surface.get_rect(center=(160,40))
    screen.blit(text_surface, rect)
    
# display the date on the home screen
def display_date():
    global date
    
    if not gps.has_fix: # if GPS not connected, can't tell the date either
        date = ''
    else:
        date = '{:02}/{:02}/{}'.format(         # get date from gps
                gps.timestamp_utc.tm_mon,
                gps.timestamp_utc.tm_mday,
                gps.timestamp_utc.tm_year)
        
    text_surface = medium_font.render(get_verbose_date(date), True, WHITE)
    rect = text_surface.get_rect(center=(160,100))
    screen.blit(text_surface, rect)
    
# convert date from form '04/30/2022' to form 'April 30, 2022'
def get_verbose_date(numeric_date):
    if numeric_date == '': # corner case when there is no GPS signal
        return ''
    parts = numeric_date.split('/')
    index = int(parts[0])-1
    months = ['Jan.', 'Feb.', 'Mar.', 'Apr.', 'May', 'Jun.', 'Jul.', 'Aug.', 'Sep.', 'Oct.', 'Nov.', 'Dec.']
    month = months[index]
    day = parts[1]
    year = parts[2]
    return month + ' ' + day + ', ' + year
    
# display data labels on bike screen
def display_data_labels():
    small_font.set_underline(True) # underline the data labels
    for text, pos in labels.items():
        text_surface = small_font.render(text, True, WHITE)
        rect = text_surface.get_rect(center=pos)
        screen.blit(text_surface, rect)
    small_font.set_underline(False)
    
# display data values on bike screen
def display_data():
    # display time
    text_surface = small_font.render(elapsed_time, True, WHITE)
    x,y = labels['time']
    y = y + 30
    rect = text_surface.get_rect(center=(x,y))
    screen.blit(text_surface, rect)
    
    # display distance
    text_surface = small_font.render(str(round(dist,2)) + ' km', True, WHITE)
    x,y = labels['distance']
    y = y + 30
    rect = text_surface.get_rect(center=(x,y))
    screen.blit(text_surface, rect)
    
    # display altitude
    text_surface = small_font.render((str(int(altitude))) + ' m', True, WHITE)
    x,y = labels['altitude']
    y = y + 30
    rect = text_surface.get_rect(center=(x,y))
    screen.blit(text_surface, rect)
    
    # display speed
    text_surface = small_font.render(str(speed) + ' km/h', True, WHITE)
    x,y = labels['speed']
    y = y + 30
    rect = text_surface.get_rect(center=(x,y))
    screen.blit(text_surface, rect)
    
    # display elevation gain
    text_surface = small_font.render(str(int(elevation_gain)) + ' m', True, WHITE)
    x,y = labels['elevation gain']
    y = y + 30
    rect = text_surface.get_rect(center=(x,y))
    screen.blit(text_surface, rect)
    
# tell user to move to better location when the GPS is not connecting
def tell_user_to_move():
    lines = {'GPS not connected.': (160,80), 'Move to location with clear sky.': (160,100)}
    for text, pos in lines.items():
        text_surface = small_font.render(text, True, WHITE)
        rect = text_surface.get_rect(center=pos)
        screen.blit(text_surface, rect)

# update altitude displayed to the user
def update_altitude():
    global altitude
    if gps.altitude_m is not None:
        altitude = gps.altitude_m

# update the elevation gain displayed to the user
def update_elevation_gain():
    global elevation_gain, first_val_alt, prev_altitude
    
    current_altitude = gps.altitude_m
    if first_val_alt: # if very first measurement, set current = previous
        prev_altitude = current_altitude
        first_val_alt = False
    altitude_diff = current_altitude - prev_altitude
    print("Altitude difference: " + str(altitude_diff))
    if abs(altitude_diff) > 3: # only record altitude changes of greater than 3 m to reduce jitter
        prev_altitude = current_altitude
        if altitude_diff > 0: # only positive elevation changes contribute to gain
            elevation_gain += altitude_diff
            print("Total elevation gain: " + str(elevation_gain))
    
# update speed displayed to the user
def update_speed():
    global speed
    
    if gps.speed_knots is not None:
        if gps.speed_knots > 1:
            speed = round(gps.speed_knots * 1.150779,1) # convert knots to km/h
        else:
            speed = 0
    
# update distance displayed to the user
def update_distance():
    global dist, first_val, prev_latitude, prev_longitude
    
    lat = gps.latitude
    lon = gps.longitude
    coord1 = (lat,lon)
    if first_val: # if very first measurement, set current = previous
        prev_latitude = lat
        prev_longitude = lon
        first_val = False  
    coord2 = (prev_latitude,prev_longitude)
    del_dist = distance.distance(coord1,coord2).km
    print("Distance difference: " + str(del_dist))
    if del_dist >= 0.05: # only update when 50 m change in position is detected to reduce jitter
        dist += del_dist
        print("Total distance: " + str(dist))
        prev_latitude = lat # current values become previous values in the next iteration
        prev_longitude = lon

# update the elapsed time displayed to the user
def update_elapsed_time():
    global elapsed_time
    
    time_diff = int(time.monotonic()-ref_time) + prev_time
    hours = int(time_diff/3600)
    minutes = int((time_diff-(hours*3600))/60)
    seconds = time_diff%60
    elapsed_time = '{:02}:{:02}:{:02}'.format(hours, minutes, seconds)

# saves data for the current activity in a file
def write_activity_to_file():
    global date, time_of_day, dist, elapsed_time, elevation_gain
    
    # convert time to 24-hour format to alphabetize file names
    if 'AM' in time_of_day:
        time_24hr = time_of_day[:-3]
    else:
        i = time_of_day.index(':')
        time_24hr = str(int(time_of_day[:i])+12) + time_of_day[i:-3]
        
    filename = date.replace('/','-') + '_' + time_24hr
    with open('/home/pi/final_project/activities/' + filename, 'w') as file:
        file.write('Date: ' + get_verbose_date(date) + '\n')
        i = time_of_day.rindex(':')
        file.write('Time of day: ' + time_of_day[:i] + time_of_day[i+3:] + '\n')
        file.write('Distance: ' + str(round(dist,1)) + ' km \n')
        file.write('Elapsed time: ' + elapsed_time + '\n')
        file.write('Elevation gain: ' + str(int(elevation_gain)) + ' m \n')

# resets the user interface to its initial state
def reset_system():                                        
    global altitude, elevation_gain, prev_altitude, speed, dist, prev_latitude
    global prev_longitude, ref_time, prev_time, first_val_alt, first_val, elapsed_time
    global start, pause, on_home_screen, on_bike_screen, on_history_screen, on_summary_screen, on_graph_screen

    altitude = elevation_gain = prev_altitude = speed = dist = 0
    prev_latitude = prev_longitude = ref_time = prev_time = 0
    first_val_alt = first_val = True
    elapsed_time = '00:00:00'
    start = pause = False
    on_home_screen = True
    on_bike_screen = on_history_screen = on_summary_screen = on_graph_screen = False

# plot and save bar graph
def plot_bars(x_axis, y_axis, title, filename):
    matplotlib.rcParams.update({'font.size': 10, 'text.color' : 'white',
                                'xtick.color': 'white', 'ytick.color': 'white'})
    fig = plt.figure(figsize = (3,2), facecolor='black')
    plt.bar(x_axis, y_axis, color = 'maroon', width=0.4)
    plt.title(title)
    plt.savefig(filename)
    plt.close()

# write weekly totals for a particular week to a summary file
def write_summary_to_file(dist_sum, time_sum, elev_sum, start_date, end_date):
    hours = int((time_sum/60))
    mins = time_sum%60
    with open('/home/pi/final_project/summaries/' + start_date.replace('/','-'), 'w') as file:
        file.write(get_verbose_date(start_date) + ' to ' + get_verbose_date(end_date) + '\n')
        file.write('Total distance: ' + str(dist_sum) + ' km \n')
        file.write('Total time: ' + str(hours) + ' hours ' + str(mins) + ' mins \n')
        file.write('Total elevation gain: ' + str(elev_sum) + ' m \n')    

# compute the start date of the week that an activity is in
def get_start_of_week(activity_filename):
    activity_datetime = activity_filename.split('-')
    activity_datetime = datetime.datetime(int(activity_datetime[2][:4]),int(activity_datetime[0]),int(activity_datetime[1]))
    day_of_week = activity_datetime.weekday()
    start_of_week = activity_datetime - datetime.timedelta(day_of_week) # start date of current week
    return start_of_week
    
# create graphs and weekly totals for distance, time, and elevation gain data
def summarize_data():
    global activities
    
    x_axis = ['M', 'Tu', 'W', 'Th', 'F', 'Sa', 'Su']
    dist_vals = [0]*7 # store distance per weekday
    time_vals = [0]*7 # time per weekday
    elev_vals = [0]*7 # elevation gain per weekday
    
    for i in range(len(activities)):
            
        # get date of activity as a datetime object
        activity_datetime = activities[i].split('-')
        activity_datetime = datetime.datetime(int(activity_datetime[2][:4]),int(activity_datetime[0]),int(activity_datetime[1]))
        day_of_week = activity_datetime.weekday()
        start_of_week = activity_datetime - datetime.timedelta(day_of_week) # start date of current week
        end_of_week = activity_datetime + datetime.timedelta(6-day_of_week) # end date of current week

        with open('/home/pi/final_project/activities/' + activities[i], 'r') as file:
            lines = file.readlines()
        for line in lines:
            if 'Distance' in line:
                dist_vals[day_of_week] += float(line.split(' ')[1])
            if 'Elapsed time' in line:
                time_str = line.split(' ')[2]
                time_str = time_str.split(':')
                hours = int(time_str[0])
                mins = int(time_str[1])
                secs = int((time_str[2])[:-1]) # remove newline character from this string
                time_in_mins = (secs + mins*60 + hours*3600)/60
                time_vals[day_of_week] += time_in_mins
            if 'Elevation gain' in line:
                elev_vals[day_of_week] += float(line.split(' ')[2])
                
        # if there are no more activity files or the next activity belongs to a different week
        if i == (len(activities)-1) or start_of_week != get_start_of_week(activities[i+1]):
            # get start and end dates of week
            start_date = start_of_week.strftime('%m/%d/%Y')
            end_date = end_of_week.strftime('%m/%d/%Y')
            
            # plot and store bar graphs for that week
            plot_bars(x_axis, dist_vals, 'Distance (km)', '/home/pi/final_project/graphs/dist_graphs/' + start_date.replace('/','-') + '.png')
            plot_bars(x_axis, time_vals, 'Time (mins)', '/home/pi/final_project/graphs/time_graphs/' + start_date.replace('/','-') + '.png')
            plot_bars(x_axis, elev_vals, 'Elevation gain (m)', '/home/pi/final_project/graphs/elev_graphs/' + start_date.replace('/','-') + '.png')
    
            # write a summary file for that week
            dist_sum = sum(dist_vals)
            time_sum = int(sum(time_vals))
            elev_sum = int(sum(elev_vals))
            write_summary_to_file(dist_sum, time_sum, elev_sum, start_date, end_date)
            
            # reset arrays for the following week
            dist_vals = [0]*7 # store distance per weekday
            time_vals = [0]*7 # time per weekday
            elev_vals = [0]*7 # elevation gain per weekday

while code_running:
    time.sleep(0.2)
    
    if (not GPIO.input(27)): # if quit button is pressed, end program
        code_running = False
        
    screen.fill(BLACK) # erase workspace
    
    # get new data from GPS every second
    current_time = time.monotonic()
    if current_time - last_time >= 1.0:
        last_time = current_time
        gps.update()
    
    # user is on the home screen
    if on_home_screen:
        display_time_of_day()
        display_date()
        
        # draw home screen buttons
        for image, position in home_screen_buttons.items():
            rect = image.get_rect(center=position)
            screen.blit(image, rect)
        
        # check if buttons were pressed
        for event in pygame.event.get():
            if (event.type is MOUSEBUTTONUP):
                pos = pygame.mouse.get_pos()
                for (image, rect) in home_screen_button_rects.items():
                    if (rect.collidepoint(pos)):
                        if (image == bike): # enter bike screen
                            on_home_screen = on_history_screen = on_summary_screen = on_graph_screen = False
                            on_bike_screen = True
                            screen.fill(BLACK) # erase workspace
                        elif (image == history): # enter history screen
                            on_home_screen = on_bike_screen = on_summary_screen = on_graph_screen = False
                            on_history_screen = True
                            activities = os.listdir('/home/pi/final_project/activities/') # get names of activity files
                            activities.sort() # list from least to most recent
                            screen_num = len(activities)-1 # always start by showing most recent activity
                            screen.fill(BLACK) # erase workspace
                        elif (image == summary): # enter summary screen
                            on_home_screen = on_bike_screen = on_history_screen = on_graph_screen = False
                            on_summary_screen = True
                            summaries = os.listdir('/home/pi/final_project/summaries/') # get names of activities
                            summaries.sort() # list from least to most recent
                            screen_num = len(summaries)-1 # always start by showing most recent summary
                            screen.fill(BLACK) # erase workspace
    
    # user is on the bike screen
    if on_bike_screen:
        
        if not gps.has_fix: # if GPS not connected, tell user to move
            tell_user_to_move()
            
            # draw back button
            for text, position in bike_screen_buttons.items():
                if text == 'back':
                    text_surface = small_font.render(text, True, WHITE)
                    rect = text_surface.get_rect(center=position)
                    screen.blit(text_surface, rect)
                
            # check if back button was pressed
            for event in pygame.event.get():
                if (event.type is MOUSEBUTTONUP):
                    pos = pygame.mouse.get_pos()
                    for (text, rect) in bike_screen_button_rects.items():
                        if (text != 'start') and (text != 'pause') and (text != 'save') and (rect.collidepoint(pos)):
                            if (text == 'back'): # press back button to return to home screen
                                on_home_screen = True
                                on_bike_screen = on_history_screen = on_summary_screen = on_graph_screen = False
                                screen.fill(BLACK) # erase workspace
        else:
            display_data_labels()
            display_data()
            update_altitude()
            update_speed()
            
            # if waiting for user to start the activity
            if not start:
                
                # draw back and start buttons
                for text, position in bike_screen_buttons.items():
                    if text != 'pause' and text != 'save':
                        text_surface = small_font.render(text, True, WHITE)
                        rect = text_surface.get_rect(center=position)
                        screen.blit(text_surface, rect)
                    
                # check if buttons were pressed
                for event in pygame.event.get():
                    if (event.type is MOUSEBUTTONUP):
                        pos = pygame.mouse.get_pos()
                        for (text, rect) in bike_screen_button_rects.items():
                            if (text != 'pause') and text != 'save' and (rect.collidepoint(pos)):
                                if (text == 'back'): # press back button to return to home screen
                                    on_home_screen = True
                                    on_bike_screen = on_history_screen = on_summary_screen = on_graph_screen = False
                                    screen.fill(BLACK) # erase workspace
                                elif (text == 'start'): # start recording activity
                                    start = True
                                    ref_time = time.monotonic() # store current time to be the reference time
                                    
            else: # user has started the activity
                if not pause: # activity is not paused
                    update_elapsed_time()
                    update_distance()
                    update_elevation_gain()
                    
                    # draw save and pause buttons buttons
                    for text, position in bike_screen_buttons.items():
                        if text != 'start' and text != 'back':
                            text_surface = small_font.render(text, True, WHITE)
                            rect = text_surface.get_rect(center=position)
                            screen.blit(text_surface, rect)
                            
                    # check if buttons were pressed
                    for event in pygame.event.get():
                        if (event.type is MOUSEBUTTONUP):
                            pos = pygame.mouse.get_pos()
                            for (text, rect) in bike_screen_button_rects.items():
                                if (text != 'start') and (text != 'back') and (rect.collidepoint(pos)):
                                    if (text == 'save'): # save activity, reset system, and summarize all past data
                                        write_activity_to_file()
                                        reset_system()
                                        activities = os.listdir('/home/pi/final_project/activities/') # get names of activities
                                        activities.sort() # show activities from least to most recent
                                        summarize_data()
                                        screen.fill(BLACK) # erase workspace
                                    elif (text == 'pause'): # pause recording of activity
                                        pause = True
                                        
                                        
                else: # activity is paused
                    # draw save and start buttons
                    for text, position in bike_screen_buttons.items():
                        if text != 'pause' and text != 'back':
                            text_surface = small_font.render(text, True, WHITE)
                            rect = text_surface.get_rect(center=position)
                            screen.blit(text_surface, rect)
                            
                    # check if buttons were pressed
                    for event in pygame.event.get():
                        if (event.type is MOUSEBUTTONUP):
                            pos = pygame.mouse.get_pos()
                            for (text, rect) in bike_screen_button_rects.items():
                                if (text != 'pause') and (text != 'back') and (rect.collidepoint(pos)):
                                    if (text == 'save'): # save activity, reset system, and summarize all past data
                                        write_activity_to_file()
                                        reset_system()
                                        activities = os.listdir('/home/pi/final_project/activities/') # get names of activities
                                        activities.sort() # show activities from least to most recent
                                        summarize_data()
                                        screen.fill(BLACK) # erase workspace
                                    elif (text == 'start'): # start recording again
                                        pause = False
                                        prev_time = int(elapsed_time[:2])*3600 + int(elapsed_time[3:5])*60 + int(elapsed_time[6:])
                                        ref_time = time.monotonic()
                                        first_val = True
                                        first_val_alt = True
                                        
    if on_history_screen: # users can go here to view past activities
        
        # draw arrow buttons
        for image, position in arrow_buttons.items():
            rect = image.get_rect(center=position)
            screen.blit(image, rect)
        
        # check if buttons were pressed
        for event in pygame.event.get():
            if (event.type is MOUSEBUTTONUP):
                pos = pygame.mouse.get_pos()
                for (image, rect) in arrow_button_rects.items():
                    if (rect.collidepoint(pos)):
                        if (image == left_arrow) and (len(activities) > 0): # view less recent activity
                            screen_num = (screen_num-1)%len(activities)
                        elif (image == right_arrow) and (len(activities) > 0): # view more recent activity
                            screen_num = (screen_num+1)%len(activities)
                        elif (image == home): # return to home screen
                                on_home_screen = True
                                on_bike_screen = on_history_screen = on_summary_screen = on_graph_screen = False
                                screen.fill(BLACK) # erase workspace
                                
        if (len(activities) > 0): # if there is at least one activity, display past activities
            with open('/home/pi/final_project/activities/' + activities[screen_num], 'r') as file:
                lines = file.readlines()
            y = 0
            for line in lines:
                text_surface = small_font.render(line[:-1], True, WHITE)
                rect = text_surface.get_rect(topleft=(0,y))
                screen.blit(text_surface, rect)
                y += 33
    
    if on_summary_screen: # users can go here to view summarized data from past activities
        
        if (len(summaries) > 0): # if there is at least one summary, display past summaries
            with open('/home/pi/final_project/summaries/' + summaries[screen_num], 'r') as file:
                lines = file.readlines()
            y = 0
            for line in lines:
                if y == 0: # underline date range of the week
                    small_font.set_underline(True)
                    text_surface = small_font.render(line[:-1], True, WHITE)
                    rect = text_surface.get_rect(center=(160,15))
                    small_font.set_underline(False)
                else:
                    text_surface = small_font.render(line[:-1], True, WHITE)
                    rect = text_surface.get_rect(topleft=(0,y))
                screen.blit(text_surface, rect)
                y += 38

        # draw arrow buttons
        for image, position in arrow_buttons.items():
            rect = image.get_rect(center=position)
            screen.blit(image, rect)
            
        # draw buttons to select graphs
        for image, position in graph_selection_buttons.items():
            rect = image.get_rect(center=position)
            screen.blit(image, rect)
        
        # check if buttons were pressed
        for event in pygame.event.get():
            if (event.type is MOUSEBUTTONUP):
                pos = pygame.mouse.get_pos()
                for (image, rect) in arrow_button_rects.items():
                    if (rect.collidepoint(pos)):
                        if (image == left_arrow) and (len(summaries) > 0): # view less recent summary
                            screen_num = (screen_num-1)%len(summaries)
                        elif (image == right_arrow) and (len(summaries) > 0): # view more recent summary
                            screen_num = (screen_num+1)%len(summaries)
                        elif (image == home): # return to home screen
                            on_home_screen = True
                            on_bike_screen = on_history_screen = on_summary_screen = on_graph_screen = False
                            screen.fill(BLACK) # erase workspace
                            
                for (image, rect) in graph_selection_button_rects.items():
                    if (rect.collidepoint(pos)):
                        on_graph_screen = True
                        on_bike_screen = on_history_screen = on_summary_screen = on_home_screen = False
                        if (image == dist_graph): # display distance graph
                            graph_path = '/home/pi/final_project/graphs/dist_graphs/'
                        elif (image == time_graph): # display time graph
                            graph_path = '/home/pi/final_project/graphs/time_graphs/'
                        elif (image == elev_graph): # display elevation gain graph
                            graph_path = '/home/pi/final_project/graphs/elev_graphs/'
                        graphs = os.listdir(graph_path)
                        graphs.sort()
                        screen.fill(BLACK) # erase workspace
         
    if on_graph_screen: # screen that displays graphical summaries
        
        # draw arrow buttons
        for image, position in arrow_buttons.items():
            rect = image.get_rect(center=position)
            screen.blit(image, rect)
        
        # check if buttons were pressed
        for event in pygame.event.get():
            if (event.type is MOUSEBUTTONUP):
                pos = pygame.mouse.get_pos()
                for (image, rect) in arrow_button_rects.items():
                    if (rect.collidepoint(pos)):
                        if (image == left_arrow): # view less recent graph
                            screen_num = (screen_num-1)%len(summaries) # note than len(summaries) == len(graphs)
                        elif (image == right_arrow): # view more recent graph
                            screen_num = (screen_num+1)%len(summaries)
                        elif (image == home): # return to summary screen
                            on_summary_screen = True
                            on_bike_screen = on_history_screen = on_home_screen = on_graph_screen = False
                            screen.fill(BLACK) # erase workspace                   

        graph = pygame.image.load(graph_path + graphs[screen_num])
        screen.blit(graph, graph.get_rect(center=(160,100))) 

    pygame.display.flip() # display everything that has been blitted
GPIO.cleanup() # always clean up GPIO when program terminates
