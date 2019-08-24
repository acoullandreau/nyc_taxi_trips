import cv2
import mysql.connector
import pandas as pd

import classfile
from utility import Utils


def parse_shapefile(shp_path, filter_on):
    base_shapefile = classfile.ShapeFile(shp_path)
    base_shapefile.build_shape_dict(base_shapefile.df_sf)

    if filter_on != []:
        filter_cond = filter_on[0]
        filter_attr = filter_on[1]
        df_filtered = base_shapefile.filter_shape_to_render(filter_cond, filter_attr)
        base_shapefile.build_shape_dict(df_filtered)

    return base_shapefile


def render_base_map(draw_dict):
    base_shapefile = draw_dict['base_shapefile']
    image_size = draw_dict['image_size']
    margins = draw_dict['margins']
    filter_on = draw_dict['filter_on']
    zoom_on = draw_dict['zoom_on']
    map_type = draw_dict['map_type']
    title = draw_dict['title']

    base_map = classfile.Map(base_shapefile, image_size)
    projection = classfile.Projection(base_map, margins)

    if zoom_on != []:
        zoom_on_cond = zoom_on[0]
        zoom_on_attr = zoom_on[1]
        zoom_shapefile = classfile.ShapeFile(shp_path)
        df_zoom = zoom_shapefile.filter_shape_to_render(zoom_on_cond, zoom_on_attr)
        zoom_shapefile.build_shape_dict(df_zoom)
        zoom_map = classfile.Map(zoom_shapefile, image_size)
        projection = classfile.Projection(zoom_map, margins)

    for zone_id in base_map.shape_dict:
        shape = base_map.shape_dict[zone_id]
        shape.project_shape_coords(projection)

    base_map.render_map()
    base_map.map_file = display_general_information_text(base_map.map_file, map_type, title)

    return base_map, projection


def display_general_information_text(image, map_type, title):

    # note that these position are based on an image size of [1920, 1080]
    font = cv2.FONT_HERSHEY_SIMPLEX

    # displays the name of the boroughs of the city
    if map_type == 'total':
        # name of borough Manhattan
        cv2.putText(image, 'Manhattan', (770, 360), font, 0.8, (255, 255, 255), 1, cv2.LINE_AA)
        # name of borough Brooklyn
        cv2.putText(image, 'Brooklyn', (1130, 945), font, 0.8, (255, 255, 255), 1, cv2.LINE_AA)
        # name of borough Staten Island
        cv2.putText(image, 'Staten Island', (595, 1030), font, 0.8, (255, 255, 255), 1, cv2.LINE_AA)
        # name of borough Queens
        cv2.putText(image, 'Queens', (1480, 590), font, 0.8, (255, 255, 255), 1, cv2.LINE_AA)
        # name of borough Bronx
        cv2.putText(image, 'Bronx', (1370, 195), font, 0.8, (255, 255, 255), 1, cv2.LINE_AA)

    else:
        title = title + ' in ' + map_type

    # displays the title of the video
    # cv2.putText(image, title, (500, 1050), font, 1, (255, 255, 255), 2, cv2.LINE_AA)


def build_query_dict(render_dict):

    # First, we extract the variables we will need from the input dictionary
    time_granularity = render_dict['time_granularity']
    filter_query_on_borough = render_dict['filter_query_on_borough']
    weekdays = render_dict['weekdays']

    # we instantiate the query_dict and start filling it with query parameters
    query_dict = {}
    query_dict['data_table'] = render_dict['data_table']
    query_dict['lookup_table'] = render_dict['lookup_table']
    query_dict['aggregated_result'] = render_dict['aggregated_result']
    query_dict['aggregate_period'] = render_dict['aggregate_period']
    query_dict['weekdays'] = weekdays

    # we handle the borough related WHEN statement
    if filter_query_on_borough is False:
        query_dict['filter_query_on_borough'] = False
    else:
        query_dict['filter_query_on_borough'] = filter_query_on_borough

    # we handle the time related WHEN statements
    period = render_dict['period']
    start_date = period[0]
    end_date = period[1]

    if start_date == end_date:
        query_dict['date'] = start_date

    else:
        # if the period is more than one date, we will have to loop through the
        # date range and render multiple series of 60 frames (1 second at 60 fps per day)
        # Thus the loop needs to be handled by the main plotting function, and here we
        # simply add a flag to the query dict that will be transformed by the plotting
        # function
        query_dict['date'] = 'loop_through_period'

    # used specifically for the animation logic
    if time_granularity == 'specific_weekdays' or weekdays != ():
        query_dict['specific_weekdays'] = 'on_specific_weekdays'

    # used specifically for the animation logic
    elif time_granularity == 'period':
        query_dict['specific_weekdays'] = False

    # used specifically for the heat_map logic
    elif time_granularity == 'weekdays_vs_weekends':
        query_dict['specific_weekdays'] = 'weekdays_vs_weekends'

    return query_dict


def make_sql_query(query, database):
    # connect to the database
    db = mysql.connector.connect(
        host="localhost",
        user="root",
        passwd="password",
        database=database
        )

    # execute the query...
    cursor = db.cursor()
    cursor.execute(query)

    # ...and store the output
    results = []
    for result in cursor:
        result.append(result)

    cursor.close()

    return results


def prepare_heat_map_sql_query(query_dict):

    # We extract the variables we will need from the input dictionary
    data_table = query_dict['data_table']
    lookup_table = query_dict['lookup_table']
    aggregated_result = query_dict['aggregated_result']
    date = query_dict['date']
    filter_query_on_borough = query_dict['filter_query_on_borough']
    weekdays_vs_weekends = query_dict['specific_weekdays']

    # first we synthesise what we want to fetch
    if aggregated_result == 'count':
        # we will want to return the sum of count on the period
        aggregated_result = 'COUNT(passenger_count_per_day)'
    elif aggregated_result == 'avg':
        # we will want to return the average of count on the period
        aggregated_result = 'AVG(passenger_count_per_day)'

    # we prepare the period statements
    if type(date) == str:
        # in this case, we want the result on a single day
        date_statement = ("pickup_date = '{}'").format(date)
    else:
        # we provided a time interval we want the average of the aggregated_result on the
        # period
        start_date = date[0]
        end_date = date[1]
        date_statement = ("pickup_date BETWEEN '{}' AND '{}'").format(start_date, end_date)

    # we build the query
    if weekdays_vs_weekends == 'weekdays_vs_weekends':
        # in this situation we want to query 'separately' the values in weekdays and weekends
        # and make a difference on the average of the aggregated_result on the period
        date_statement_weekdays = ("pickup_date BETWEEN '{}' AND '{}' AND pickup_weekday IN (0, 1, 2, 3, 4)".format(start_date, end_date))
        date_statement_weekends = ("pickup_date BETWEEN '{}' AND '{}' AND pickup_weekday IN (5, 6)".format(start_date, end_date))

        # Case 1: we want to compare weekdays and weekends flow for a specific borough
        if filter_query_on_borough is not False:
            query = ("SELECT pu_id, do_id, diff \
                    FROM (SELECT wd_pu_id pu_id, wd_do_id do_id, wd_aggregated_result - we_aggregated_result diff\
                        FROM(SELECT CASE WHEN wd_pu_id IS NULL THEN we_pu_id ELSE wd_pu_id END AS wd_pu_id, \
                                    CASE WHEN wd_do_id IS NULL THEN we_do_id ELSE wd_do_id END AS wd_do_id,\
                                    CASE WHEN wd_aggregated_result IS NULL THEN 0 ELSE wd_aggregated_result END AS wd_aggregated_result,\
                                    CASE WHEN we_pu_id IS NULL THEN wd_pu_id ELSE we_pu_id END AS we_pu_id, \
                                    CASE WHEN we_do_id IS NULL THEN wd_do_id ELSE we_do_id END AS we_do_id,\
                                    CASE WHEN we_aggregated_result IS NULL THEN 0 ELSE we_aggregated_result END AS we_aggregated_result\
                        FROM (SELECT *\
                                FROM (SELECT PULocationID wd_pu_id, DOLocationID wd_do_id, {0} wd_aggregated_result\
                                    FROM {1}\
                                    WHERE {2} \
                                    GROUP BY wd_pu_id, wd_do_id) as weekdays\
                                LEFT JOIN (SELECT PULocationID we_pu_id, DOLocationID we_do_id, {0} we_aggregated_result\
                                        FROM {1}\
                                        WHERE {3} \
                                        GROUP BY we_pu_id, we_do_id) as weekends\
                                ON weekdays.wd_pu_id = weekends.we_pu_id \
                                    AND weekdays.wd_do_id = weekends.we_do_id\
                            UNION \
                                SELECT *\
                                FROM (SELECT PULocationID wd_pu_id, DOLocationID wd_do_id, {0} wd_aggregated_result\
                                        FROM {1}\
                                        WHERE {2} \
                                        GROUP BY wd_pu_id, wd_do_id) as weekdays\
                                RIGHT JOIN (SELECT PULocationID we_pu_id, DOLocationID we_do_id, {0} we_aggregated_result\
                                            FROM {1}\
                                            WHERE {3} \
                                            GROUP BY we_pu_id, we_do_id) as weekends\
                                ON weekdays.wd_pu_id = weekends.we_pu_id \
                                 AND weekdays.wd_do_id = weekends.we_do_id) as tab_1) as tab_2\
                    JOIN {4} lookup_pu\
                    ON lookup_pu.LocationID = tab_2.pu_id \
                    JOIN {4} lookup_do \
                    ON lookup_do.LocationID = tab_2.do_id \
                    WHERE lookup_pu.borough_name = '{5}' AND lookup_do.borough_name = '{5}'\
                    GROUP BY pu_id, do_id, diff;".format(aggregated_result, data_table,
                                                         date_statement_weekdays,
                                                         date_statement_weekends,
                                                         lookup_table,
                                                         filter_query_on_borough))

        # Case 2: we want to compare weekdays and weekends flow for the whole city
        else:
            query = ("SELECT wd_pu_id pu_id, wd_do_id do_id, wd_aggregated_result - we_aggregated_result diff\
                    FROM(SELECT CASE WHEN wd_pu_id IS NULL THEN we_pu_id ELSE wd_pu_id END AS wd_pu_id, \
                                CASE WHEN wd_do_id IS NULL THEN we_do_id ELSE wd_do_id END AS wd_do_id,\
                                CASE WHEN wd_aggregated_result IS NULL THEN 0 ELSE wd_aggregated_result END AS wd_aggregated_result,\
                                CASE WHEN we_pu_id IS NULL THEN wd_pu_id ELSE we_pu_id END AS we_pu_id, \
                                CASE WHEN we_do_id IS NULL THEN wd_do_id ELSE we_do_id END AS we_do_id,\
                                CASE WHEN we_aggregated_result IS NULL THEN 0 ELSE we_aggregated_result END AS we_aggregated_result\
                    FROM (SELECT *\
                            FROM (SELECT PULocationID wd_pu_id, DOLocationID wd_do_id, {0} wd_aggregated_result\
                                FROM {1}\
                                WHERE {2} \
                                GROUP BY wd_pu_id, wd_do_id) as weekdays\
                            LEFT JOIN (SELECT PULocationID we_pu_id, DOLocationID we_do_id, {0} we_aggregated_result\
                                    FROM {1}\
                                    WHERE {3} \
                                    GROUP BY we_pu_id, we_do_id) as weekends\
                            ON weekdays.wd_pu_id = weekends.we_pu_id \
                                AND weekdays.wd_do_id = weekends.we_do_id\
                        UNION \
                            SELECT *\
                            FROM (SELECT PULocationID wd_pu_id, DOLocationID wd_do_id, {0} wd_aggregated_result\
                                    FROM {1}\
                                    WHERE {2} \
                                    GROUP BY wd_pu_id, wd_do_id) as weekdays\
                            RIGHT JOIN (SELECT PULocationID we_pu_id, DOLocationID we_do_id, {0} we_aggregated_result\
                                        FROM {1}\
                                        WHERE {3} \
                                        GROUP BY we_pu_id, we_do_id) as weekends\
                            ON weekdays.wd_pu_id = weekends.we_pu_id \
                             AND weekdays.wd_do_id = weekends.we_do_id) as tab_1) as tab_2;".format(aggregated_result, data_table, date_statement_weekdays, date_statement_weekends))

    else:
        # Case 3: we want the total average/count on the period for a specific borough
        if filter_query_on_borough is not False:
            query = ("SELECT pu_id, do_id, {0} aggregated_result \
                    FROM \
                         (SELECT PULocationID pu_id, DOLocationID do_id, \
                                 passenger_count_per_day\
                        FROM {1}\
                        WHERE {2} \
                        GROUP BY pu_id, do_id) as tab_1 \
                    JOIN {3} lookup_pu\
                    ON lookup_pu.LocationID = tab_1.pu_id \
                    JOIN {3} lookup_do \
                    ON lookup_do.LocationID = tab_1.do_id \
                    WHERE lookup_pu.borough_name = '{4}' AND lookup_do.borough_name = '{4}'\
                    GROUP BY pu_id, do_id".format(aggregated_result, data_table, date_statement, lookup_table, filter_query_on_borough))

        # Case 4: we want the total average/count on the period for the whole city
        else:
            query = ("SELECT PULocationID pu_id, DOLocationID do_id, {0} aggregated_result\
                    FROM {1}\
                    WHERE {2} \
                    GROUP BY pu_id, do_id".format(aggregated_result, data_table, date_statement))

    return query


def process_heat_map_query_results(query_results, base_shapefile):

    incoming_flow = {}
    outgoing_flow = {}

    for itinerary in query_results:
        origin_id = itinerary[0]
        destination_id = itinerary[1]
        weight = itinerary[2]
        shape_origin = classfile.ShapeOnMap(base_shapefile, origin_id)
        shape_destination = classfile.ShapeOnMap(base_shapefile, destination_id)
        # We build a dictionary of outgoing traffic
        if shape_origin not in outgoing_flow:
            outgoing_flow[shape_origin] = []
        outgoing_flow[shape_origin].append((shape_destination, weight))
        # We build a dictionary of incoming traffic
        if shape_destination not in incoming_flow:
            incoming_flow[shape_destination] = []
        incoming_flow[shape_destination].append((shape_origin, weight))

    return outgoing_flow, incoming_flow


# Main flow of the script

# shp_path = "/Users/acoullandreau/Desktop/Taxi_rides_DS/taxi_zones/taxi_zones.shp"

# chlor_map_dict = {'image_size': (1920, 1080),'margins': (), 'db':'nyc_taxi_rides',
#                   'maps_to_render': ['total', 'Manhattan', 'Bronx', 'Queens', 'Staten Island', 'Brooklyn'],
#                   'filter_on': [], 'zoom_on': [], 'filter_query_on_borough': False,
#                   'data_table':'passenger_count_2018','lookup_table':'taxi_zone_lookup_table',
#                   'aggregated_result':'count', 'weekdays_vs_weekends':False,
#                   'period':['2018-01-01','2018-01-31'], 'title':'Chloropeth map over the year'}


chlor_map_dict = {}
shp_path = input("Enter the path of the shapefile: ")
dict_input = input("Enter key and value separated by commas (,): ")

key, value = dict_input.split(",")
animation_dict[key] = value

# we extract the variables from the input dictionary
image_size = chlor_map_dict['image_size']
margin = chlor_map_dict['margin']
maps_to_render = chlor_map_dict['maps_to_render']
filter_on = chlor_map_dict['filter_on']
zoom_on = chlor_map_dict['zoom_on']
title = chlor_map_dict['title']
database = chlor_map_dict['db']
data_table = chlor_map_dict['data_table']
lookup_table = chlor_map_dict['lookup_table']
aggregated_result = chlor_map_dict['aggregated_result']
filter_query_on_borough = chlor_map_dict['filter_query_on_borough']
period = chlor_map_dict['period']
weekdays_vs_weekends = chlor_map_dict['weekdays_vs_weekends']

if chlor_map_dict['weekdays_vs_weekends'] is True:
    time_granularity = 'weekdays_vs_weekends'
else:
    time_granularity = 'period'

print('Building the base map...')

# Parse the shapefile

base_shapefile = parse_shapefile(shp_path, filter_on)

# Draw the base map and keep it in a saved variable
base_maps = []

if len(maps_to_render) == 1:
    if maps_to_render[0] == 'total':
        zoom_on = []
    else:
        zoom_on = [maps_to_render[0], 'borough']

    # we want to render on a single map
    draw_dict = {'image_size': image_size, 'margins': (), 'filter_on': [],
                 'zoom_on': zoom_on, 'map_type': maps_to_render[0],
                 'title': title, 'base_shapefile': base_shapefile}
    base_map, projection = render_base_map(draw_dict)
    base_maps.append((maps_to_render[0], base_map, projection))

else:
    # we want to render multiple animations at once, for different base maps
    for single_map in maps_to_render:
        if single_map == 'total':
            zoom_on = []
        else:
            zoom_on = [single_map, 'borough']
        draw_dict = {'image_size': image_size, 'margins': (), 'filter_on': [],
                     'zoom_on': zoom_on, 'map_type': single_map, 'title': title,
                     'base_shapefile': base_shapefile}

        base_map, projection = render_base_map(draw_dict)
        base_maps.append((single_map, base_map, projection))

# we build the query statement and execute it on the database
print('Querying the dabase...')
query_dict = build_query_dict(render_heat_map_dict)

if query_dict['date'] == 'loop_through_period':
    # if we have the flag loop_through_period in the query dict, it means the period
    # set for the query is multiple dates, therefore we want the query to return an
    # average on a time interval, and not on a single date
    period = render_heat_map_dict['period']
    daterange = pd.date_range(period[0],period[1])
    query_dict['date'] = period

query = prepare_heat_map_sql_query(query_dict)
query_results = make_sql_query(query, database)

# we process the query results
outgoing_flow, incoming_flow = process_heat_map_query_results(query_results,
                                                              base_shapefile)





    
    draw_dict = render_heat_map_dict['draw_dict']
    flow_dict = render_heat_map_dict['flow_dict']
    flow_dir = render_heat_map_dict['flow_dir']
    time_granularity = render_heat_map_dict['time_granularity']
    df_sf = draw_dict['df_sf']
    
    
    for zone_id in flow_dict:
        #we ensure the ids are in the write 'system'
        trips_list = flow_dict[zone_id]
        i = 0
        for trip in trips_list:
            dest_id = convert_id_shape(trip[0])
            trips_list[i] = (dest_id, trip[1])
            i+=1
        zone_id = convert_id_shape(zone_id)
        
        
        #first let's figure out in which borough it is, and which name it has
        zone_name, borough_name = find_names(zone_id, df_sf)
        
        #we want to render the base map on the whole NYC map, as well as on a borough
        #zoomed map
        
        #Let's build the file names
        zone_id_lookup = convert_id_shape(zone_id, inverse=True)
        if time_granularity == 'weekdays_vs_weekends':
            nyc_file_name = 'NYC_{}_{}_{}_2018_diff_WD_WE'.format(zone_id_lookup, zone_name, flow_dir)
            borough_file_name = '{}_{}_{}_{}_2018_diff_WD_WE'.format(borough_name, zone_id_lookup, 
                                                                     zone_name, flow_dir)
        else:
            nyc_file_name = 'NYC_{}_{}_{}_2018'.format(zone_id_lookup, zone_name, flow_dir)
            borough_file_name = '{}_{}_{}_{}_2018'.format(borough_name,zone_id_lookup, 
                                                          zone_name, flow_dir)
        
        zone_info = [zone_id_lookup, zone_name]
        
        #we get the min and max number of passengers and color the linked zones
        min_passenger, max_passenger = compute_min_max_passengers(trips_list, 1)
    
        #Render results on the NYC map
        render_map_dict_NYC = {'map_to_render':'total', 'zone_id': zone_id, 
                               'draw_dict':draw_dict, 'min_passenger':min_passenger, 
                               'max_passenger':max_passenger, 'trips_list':trips_list}
        
        nyc_map, nyc_colors = render_map(render_map_dict_NYC)
        
        #display the legend
        display_specific_text_heat_map(nyc_map, time_granularity, zone_info, 
                                       min_passenger, max_passenger, nyc_colors)

        #save the image
        cv2.imwrite(('{}.png').format(nyc_file_name),nyc_map)
        
    

        #Render results on the borough map
        render_map_dict_borough = {'map_to_render':borough_name, 'zone_id': zone_id, 
                                   'draw_dict':draw_dict, 'min_passenger':min_passenger, 
                                   'max_passenger':max_passenger, 'trips_list':trips_list}
        
        borough_map, borough_colors = render_map(render_map_dict_borough)
        
        #display the legend
        display_specific_text_heat_map(borough_map, time_granularity, zone_info, 
                                       min_passenger, max_passenger, borough_colors)
        

        #save the image
        cv2.imwrite(('{}.png').format(borough_file_name),borough_map)







    #we define the render_heat_map_dict    
    render_heat_map_dict = {'time_granularity':time_granularity, 'period':period,  
                             'image_size':image_size,'data_table':data_table, 
                             'lookup_table':lookup_table,'aggregated_result':aggregated_result,
                             'title':title, 'filter_query_on_borough':filter_query_on_borough}
    

    
    


    draw_dict = {'image_size':image_size, 'render_single_borough':render_single_borough, 
             'title':title, 'shape_dict':shape_boundaries, 'df_sf':df_sf}
    
    print('Building the outgoing maps...')
    #we build the maps for the outgoing flow
    render_heat_map_dict_out = {'draw_dict':draw_dict, 'flow_dict':outgoing_flow, 
                            'flow_dir': 'out','time_granularity':time_granularity}
    
    render_heat_map_query_output(render_heat_map_dict_out)  
    
    print('Building the incoming maps...')
    #we build the maps for the incoming flow
    render_heat_map_dict_in = {'draw_dict':draw_dict, 'flow_dict':incoming_flow, 
                            'flow_dir': 'in','time_granularity':time_granularity}
    
    render_heat_map_query_output(render_heat_map_dict_in) 


# we find the min and max passengers for the whole year
min_passenger = 999999999
max_passenger = 0
for query_date in query_results_dict:
    temp_min, temp_max = compute_min_max_passengers(query_results_dict[query_date], 2)
    if temp_min < min_passenger:
        min_passenger = temp_min
    if temp_max > max_passenger:
        max_passenger = temp_max

frame_dict = {'query_results_dict': query_results_dict,
              'base_map': base_map, 'min_passenger': min_passenger,
              'max_passenger': max_passenger, 'agg_per': aggregate_period}

# we render the animation!
for single_map, base_map, projection in base_maps:
    print('Rendering {}...'.format(single_map))
    frame_dict['single_map'] = single_map
    frames = render_frames(frame_dict)
    make_video_animation(frames, image_size, single_map)
    print('Animation for {} rendered...'.format(single_map))









def find_names(zone_id, df_sf):

    zone_name = df_sf[df_sf.index == zone_id]['zone'].item()
    borough_name = df_sf[df_sf.index == zone_id]['borough'].item()

    return zone_name, borough_name


def compute_color(weight, min_passenger, max_passenger):

    # we use a color palette that spans between two very different colors, the idea
    # being to be able to distinguish positive from negative values

    max_pos_colour = (100, 100, 255)  # shade of red
    min_pos_colour = (40, 40, 100)  # shade of red
    min_neg_colour = (0, 0, 0)  # shade of blue
    max_neg_colour = (210, 150, 90)  # shade of blue

    if weight == 0:
        color = [40, 40, 40]  # grey

    else:

        if min_passenger == max_passenger:
            # in this case we have basically one color to represent only
            if weight > 0:
                color = max_pos_colour

            else:
                color = max_neg_colour

        elif min_passenger >= 0 and max_passenger > 0:
            # in this case we draw everything in shades of red
            weight_norm = weight/max_passenger
            blue_index = (max_pos_colour[0]-min_pos_colour[0])*weight_norm + min_pos_colour[0]
            green_index = (max_pos_colour[1]-min_pos_colour[1])*weight_norm + min_pos_colour[1]
            red_index = (max_pos_colour[2]-min_pos_colour[2])*weight_norm + min_pos_colour[2]
            color = (blue_index, green_index, red_index)

        elif min_passenger < 0 and max_passenger <= 0:
            # in this case we draw everything in shades of blue
            weight_norm = weight/min_passenger
            blue_index = (max_neg_colour[0]-min_neg_colour[0])*weight_norm + min_neg_colour[0]
            green_index = (max_neg_colour[1]-min_neg_colour[1])*weight_norm + min_neg_colour[1]
            red_index = (max_neg_colour[2]-min_neg_colour[2])*weight_norm + min_neg_colour[2]
            color = (blue_index, green_index, red_index)

        else:
            # in this case the color depends on the sign of the weight
            # we call this function recursively
            if weight > 0:
                color = compute_color(weight, 0, max_passenger)

            else:
                color = compute_color(weight, min_passenger, 0)

    return color


def render_map(render_map_dict):

    # first we extract the arguments we are going to need
    map_to_render = render_map_dict['map_to_render']
    zone_id = render_map_dict['zone_id']
    trips_list = render_map_dict['trips_list']
    draw_dict = render_map_dict['draw_dict']
    shape_dict = draw_dict['shape_dict']
    draw_dict['map_type'] = map_to_render
    min_passenger = render_map_dict['min_passenger']
    max_passenger = render_map_dict['max_passenger']

    base_map, projection = draw_base_map(draw_dict)

    # we obtain the converted_shape_dict we want to use to draw the heat map
    converted_shape_dict = convert_shape_boundaries(shape_dict, projection)

    # we keep track of how many colors we use to plot the legend afterwards
    colors = []
    for linked_zone in trips_list:
        id_shape_to_color = linked_zone[0]
        if id_shape_to_color != zone_id:
            weight = linked_zone[1]
            linked_shape = converted_shape_dict[id_shape_to_color]
            linked_points = linked_shape['points']
            pts = np.array(linked_points, np.int32)
            linked_color = compute_color(weight, min_passenger, max_passenger)
            if linked_color not in colors:
                colors.append(linked_color)
            cv2.fillPoly(base_map, [pts], linked_color)
            cv2.polylines(base_map, [pts], True, (255, 255, 255), 1, cv2.LINE_AA)

    # we highlight the focused shape
    target_shape = converted_shape_dict[zone_id]
    target_points = target_shape['points']
    pts = np.array(target_points, np.int32)
    target_color = [95, 240, 255]
    cv2.polylines(base_map, [pts], True, target_color, 3, cv2.LINE_AA)

    return base_map, colors


 def display_scale_legend(map_image, font, min_pass, max_pass, colors):
    # we dynamically print a legend using a fixed step between two colors plotted
    
    k = 0
    top_bar_x = 30
    top_bar_y = 440
    
    #we add a legend for no passengers traveling
    cv2.rectangle(map_image,(top_bar_x, top_bar_y),(top_bar_x+40, top_bar_y + 20),(255, 255, 255),1)
    cv2.putText(map_image, 'No flow of people', (top_bar_x + 70, top_bar_y + 15), font, 0.7, (221, 221, 221), 1, cv2.LINE_AA)
    top_bar_y = top_bar_y + 22   
        
    #we prepare the ground to plot a dynamic legend for the colors
    if len(colors) < 8:
        scale_step = len(colors)
    else:
        scale_step = 8
    
    levels = []
    while k < scale_step:
        if scale_step > 1:
            level = max_pass + (min_pass - max_pass) * k/(scale_step-1)
        else:
            level = max_pass
        levels.append(level)
        k+=1
    
    #we check if there are negative and positive values to represent and if we already
    #have a 0 to represent ; if not, we will add it to the list of steps to plot
    neg_value_count = 0
    pos_value_count = 0
    zero_count = 0
    for level in levels:
        if level < 0:
            neg_value_count+= 1
        elif level == 0:
            zero_count+=1
        else:
            pos_value_count+=1
    
    if zero_count == 0:
        if neg_value_count > 0 and pos_value_count> 0:
            levels.append(0)
    
    #we plot dynamically the legend
    levels.sort()
    for level in levels:   
        color = compute_color(level, min_pass, max_pass)
        level = "{0:.2f}".format(level)
        cv2.rectangle(map_image,(top_bar_x, top_bar_y),(top_bar_x+40, top_bar_y + 20),color,-1)
        if float(level) == 0 or abs(float(level)) == 1:
            cv2.putText(map_image, '{} passenger'.format(level), (top_bar_x + 70, top_bar_y + 15), font, 0.7, (221, 221, 221), 1, cv2.LINE_AA)
        else:
            cv2.putText(map_image, '{} passengers'.format(level), (top_bar_x + 70, top_bar_y + 15), font, 0.7, (221, 221, 221), 1, cv2.LINE_AA)
        top_bar_y = top_bar_y + 20
    
      

def display_specific_text_heat_map(map_image, time_granularity, zone_info, min_pass, max_pass, colors):
    
    #note that these position are based on an image size of [1920, 1080]
    font = cv2.FONT_HERSHEY_SIMPLEX
    
    if time_granularity == 'period':
        time_granularity_1 = 'Flow over the whole year'
        time_granularity_2 = ""
    else:
        time_granularity_1 = "Difference between weekdays"
        time_granularity_2 = "and weekends flow"
    
    #display the main title
    cv2.putText(map_image, time_granularity_1, (30, 150), font, 1.3, (221, 221, 221), 1, cv2.LINE_AA)
    cv2.putText(map_image, time_granularity_2, (30, 180), font, 1.3, (221, 221, 221), 1, cv2.LINE_AA)
    
    #display the zone id and name
    cv2.putText(map_image, '{} - '.format(zone_info[0]), (30, 240), font, 1.3, (221, 221, 221), 1, cv2.LINE_AA)
    cv2.putText(map_image, '{}'.format(zone_info[1]), (170, 240), font, 1.3, (221, 221, 221), 1, cv2.LINE_AA)
    
    #displays the legend of the colour code
    cv2.putText(map_image, 'Legend', (30,320), font, 0.9, (221, 221, 221), 1, cv2.LINE_AA)
    cv2.rectangle(map_image,(30,340),(70,360),(95, 240, 255),3)
    cv2.putText(map_image, 'Target zone', (100, 360), font, 0.7, (221, 221, 221), 1, cv2.LINE_AA)
    cv2.putText(map_image, 'Average number of passengers', (30, 410), font, 0.7, (221, 221, 221), 1, cv2.LINE_AA)
    cv2.putText(map_image, '* A negative value means more flow on weekends', (30, 430), font, 0.5, (221, 221, 221), 1, cv2.LINE_AA)
    
    display_scale_legend(map_image, font, min_pass, max_pass, colors)

    


def render_heat_map_query_output(render_heat_map_dict):
    
    draw_dict = render_heat_map_dict['draw_dict']
    flow_dict = render_heat_map_dict['flow_dict']
    flow_dir = render_heat_map_dict['flow_dir']
    time_granularity = render_heat_map_dict['time_granularity']
    df_sf = draw_dict['df_sf']
    
    
    for zone_id in flow_dict:
        #we ensure the ids are in the write 'system'
        trips_list = flow_dict[zone_id]
        i = 0
        for trip in trips_list:
            dest_id = convert_id_shape(trip[0])
            trips_list[i] = (dest_id, trip[1])
            i+=1
        zone_id = convert_id_shape(zone_id)
        
        
        #first let's figure out in which borough it is, and which name it has
        zone_name, borough_name = find_names(zone_id, df_sf)
        
        #we want to render the base map on the whole NYC map, as well as on a borough
        #zoomed map
        
        #Let's build the file names
        zone_id_lookup = convert_id_shape(zone_id, inverse=True)
        if time_granularity == 'weekdays_vs_weekends':
            nyc_file_name = 'NYC_{}_{}_{}_2018_diff_WD_WE'.format(zone_id_lookup, zone_name, flow_dir)
            borough_file_name = '{}_{}_{}_{}_2018_diff_WD_WE'.format(borough_name, zone_id_lookup, 
                                                                     zone_name, flow_dir)
        else:
            nyc_file_name = 'NYC_{}_{}_{}_2018'.format(zone_id_lookup, zone_name, flow_dir)
            borough_file_name = '{}_{}_{}_{}_2018'.format(borough_name,zone_id_lookup, 
                                                          zone_name, flow_dir)
        
        zone_info = [zone_id_lookup, zone_name]
        
        #we get the min and max number of passengers and color the linked zones
        min_passenger, max_passenger = compute_min_max_passengers(trips_list, 1)
    
        #Render results on the NYC map
        render_map_dict_NYC = {'map_to_render':'total', 'zone_id': zone_id, 
                               'draw_dict':draw_dict, 'min_passenger':min_passenger, 
                               'max_passenger':max_passenger, 'trips_list':trips_list}
        
        nyc_map, nyc_colors = render_map(render_map_dict_NYC)
        
        #display the legend
        display_specific_text_heat_map(nyc_map, time_granularity, zone_info, 
                                       min_passenger, max_passenger, nyc_colors)

        #save the image
        cv2.imwrite(('{}.png').format(nyc_file_name),nyc_map)
        
    

        #Render results on the borough map
        render_map_dict_borough = {'map_to_render':borough_name, 'zone_id': zone_id, 
                                   'draw_dict':draw_dict, 'min_passenger':min_passenger, 
                                   'max_passenger':max_passenger, 'trips_list':trips_list}
        
        borough_map, borough_colors = render_map(render_map_dict_borough)
        
        #display the legend
        display_specific_text_heat_map(borough_map, time_granularity, zone_info, 
                                       min_passenger, max_passenger, borough_colors)
        

        #save the image
        cv2.imwrite(('{}.png').format(borough_file_name),borough_map)
        

