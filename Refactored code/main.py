import cv2
import mysql.connector
import pandas as pd

import classfile
from utility import Utils


def render_base_map(draw_dict):
    image_size = draw_dict['image_size']
    margins = draw_dict['margins']
    filter_on = draw_dict['filter_on']
    zoom_on = draw_dict['zoom_on']
    map_type = draw_dict['map_type']
    title = draw_dict['title']

    base_shapefile = classfile.ShapeFile(shp_path)
    base_shapefile.build_shape_dict(base_shapefile.df_sf)

    if filter_on != []:
        filter_cond = filter_on[0]
        filter_attr = filter_on[1]
        df_filtered = base_shapefile.filter_shape_to_render(filter_cond, filter_attr)
        base_shapefile.build_shape_dict(df_filtered)

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


def build_query_dict(render_animation_dict):

    # First, we extract the variables we will need from the input dictionary
    time_granularity = render_animation_dict['time_granularity']
    filter_query_on_borough = render_animation_dict['filter_query_on_borough']
    weekdays = render_animation_dict['weekdays']

    # we instantiate the query_dict and start filling it with query parameters
    query_dict = {}
    query_dict['data_table'] = render_animation_dict['data_table']
    query_dict['lookup_table'] = render_animation_dict['lookup_table']
    query_dict['aggregated_result'] = render_animation_dict['aggregated_result']
    query_dict['aggregate_period'] = render_animation_dict['aggregate_period']
    query_dict['weekdays'] = weekdays

    # we handle the borough related WHEN statement
    if filter_query_on_borough is False:
        query_dict['filter_query_on_borough'] = False
    else:
        query_dict['filter_query_on_borough'] = filter_query_on_borough

    # we handle the time related WHEN statements
    period = render_animation_dict['period']
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


def prepare_sql_query(query_dict):

    # We extract the variables we will need from the input dictionary
    data_table = query_dict['data_table']
    lookup_table = query_dict['lookup_table']
    aggregated_result = query_dict['aggregated_result']
    date = query_dict['date']
    filter_query_on_borough = query_dict['filter_query_on_borough']
    aggregate_period = query_dict['aggregate_period']
    weekdays = query_dict['weekdays']

    # first we synthesise what we want to fetch
    if aggregated_result == 'count':
        aggregated_result = 'COUNT(passenger_count)'
    elif aggregated_result == 'avg':
        aggregated_result = 'AVG(passenger_count)'

    # then we work on the 'WHERE' statements and the JOIN
    if aggregate_period is True:
        start_date = date[0]
        end_date = date[1]

        if weekdays == ():
            if filter_query_on_borough is not False:
                query = ("SELECT pu_id, do_id, aggregated_result FROM (\
                            SELECT PULocationID pu_id, DOLocationID do_id, {0} aggregated_result\
                            FROM {1} tr_2018\
                            WHERE pickup_date BETWEEN '{2}' AND '{3}'\
                            GROUP BY pu_id, do_id\
                            ORDER by aggregated_result\
                        ) AS tr_2018\
                         JOIN {4} lookup_pu\
                         ON lookup_pu.LocationID = tr_2018.pu_id \
                         JOIN {4} lookup_do \
                         ON lookup_do.LocationID = tr_2018.do_id \
                         WHERE lookup_pu.borough_name = '{5}' AND lookup_do.borough_name = '{5}'".format(aggregated_result, data_table, start_date, end_date, lookup_table, filter_query_on_borough))

            else:
                query = ("SELECT PULocationID pu_id, DOLocationID do_id, {0} aggregated_result\
                            FROM {1} AS tr_2018\
                            WHERE pickup_date BETWEEN '{2}' AND '{3}'\
                            GROUP BY pu_id, do_id".format(aggregated_result, data_table, start_date, end_date))

        else:
            if filter_query_on_borough is not False:
                query = ("SELECT pu_id, do_id, aggregated_result FROM (\
                            SELECT PULocationID pu_id, DOLocationID do_id, {0} aggregated_result\
                            FROM {1} tr_2018\
                            WHERE pickup_date BETWEEN '{2}' AND '{3}' AND pickup_weekday IN {4}\
                            GROUP BY pu_id, do_id\
                            ORDER by aggregated_result\
                        ) AS tr_2018\
                         JOIN {5} lookup_pu\
                         ON lookup_pu.LocationID = tr_2018.pu_id \
                         JOIN {5} lookup_do \
                         ON lookup_do.LocationID = tr_2018.do_id \
                         WHERE lookup_pu.borough_name = '{6}' AND lookup_do.borough_name = '{6}'".format(aggregated_result, data_table, start_date, end_date, weekdays, lookup_table, filter_query_on_borough))

            else:
                query = ("SELECT PULocationID pu_id, DOLocationID do_id, {0} aggregated_result\
                            FROM {1} AS tr_2018\
                            WHERE pickup_date BETWEEN '{2}' AND '{3}' AND pickup_weekday IN {4}\
                            GROUP BY pu_id, do_id".format(aggregated_result, data_table, start_date, end_date, weekdays))

    else:
        if filter_query_on_borough is not False:
            query = ("SELECT pu_id, do_id, aggregated_result FROM (\
                        SELECT PULocationID pu_id, DOLocationID do_id, {0} aggregated_result\
                        FROM {1} tr_2018\
                        WHERE pickup_date = '{2}'\
                        GROUP BY pu_id, do_id\
                        ORDER by aggregated_result\
                    ) AS tr_2018\
                     JOIN {3} lookup_pu\
                     ON lookup_pu.LocationID = tr_2018.pu_id \
                     JOIN {3} lookup_do \
                     ON lookup_do.LocationID = tr_2018.do_id \
                     WHERE lookup_pu.borough_name = '{4}' AND lookup_do.borough_name = '{4}'".format(aggregated_result, data_table, date, lookup_table, filter_query_on_borough))

        else:
            query = ("SELECT PULocationID pu_id, DOLocationID do_id, {0} aggregated_result\
                        FROM {1} AS tr_2018\
                        WHERE pickup_date = '{2}'\
                        GROUP BY pu_id, do_id".format(aggregated_result, data_table, date))

    return query


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


def process_query_arg(render_animation_dict):
    period = render_animation_dict['period']
    query_dict = render_animation_dict['query_dict']
    database = render_animation_dict['database']
    specific_weekdays = query_dict['specific_weekdays']
    date = query_dict['date']
    aggregate_period = render_animation_dict['aggregate_period']
    weekdays = render_animation_dict['weekdays']

    query_results_dict = {}

    if aggregate_period is False and query_dict['date'] == 'loop_through_period':
        # in this case we want the result for each day of the period provided
        # if we have the flag loop_through_period in the query dict, it means the period
        # set for the query is multiple dates

        daterange = pd.date_range(period[0], period[1])
        # we run queries for each date in the daterange specified
        for single_date in daterange:
            date = pd.to_datetime(single_date)
            if specific_weekdays == 'on_specific_weekdays':

                # we check if the date of the daterange matches the weekday(s) we target
                if date.dayofweek in weekdays:
                    single_date = date.date().strftime('%Y-%m-%d')
                    query_dict['date'] = single_date
                    query = prepare_sql_query(query_dict)
                    query_results = make_sql_query(query, database)
                    query_results_dict[query_dict['date']] = query_results

                else:
                    # if a date in the range is not among the weekdays we want, we skip it
                    continue
            else:
                single_date = date.date().strftime('%Y-%m-%d')
                query_dict['date'] = single_date
                query = prepare_sql_query(query_dict)
                query_results = make_sql_query(query, database)
                query_results_dict[query_dict['date']] = query_results

    elif aggregate_period is True and query_dict['date'] == 'loop_through_period':
        # in this case, we want to aggregate the results (sum) per week
        daterange = pd.date_range(period[0], period[1])
        start_date = pd.to_datetime(period[0])
        end_date = pd.to_datetime(period[1])

        # let's build a list of all intervals we will want to aggregate the data for
        all_aggr_init = []
        start = start_date
        end = end_date

        # we add one list of dates per week to the list of all intervals
        i = 0
        for date in daterange:
            # we handle separately the first date of the period
            if i == 0:
                curr_week = [start.date().strftime('%Y-%m-%d')]

            if date != start_date and date != end_date:
                start_week_number = start.isocalendar()[1]
                date_week_number = date.isocalendar()[1]

                if date_week_number == start_week_number:
                    curr_week.append(date.date().strftime('%Y-%m-%d'))
                    i += 1
                else:
                    start = date
                    all_aggr_init.append(curr_week)
                    i = 0

        # we handle separately the last date of the period
        if curr_week not in all_aggr_init:
            curr_week.append(end_date.date().strftime('%Y-%m-%d'))
            all_aggr_init.append(curr_week)
        else:
            curr_week = [end_date.date().strftime('%Y-%m-%d')]
            all_aggr_init.append(curr_week)

        # now we keep only the first and last item of each interval

        all_aggr = []
        for interval in all_aggr_init:
            interval_new = [interval[0], interval[-1]]
            all_aggr.append(interval_new)

        # we now query for each interval
        for interval in all_aggr:
            query_dict['date'] = interval
            query = prepare_sql_query(query_dict)
            query_results = make_sql_query(query, database)
            query_results_dict[query_dict['date'][0]] = query_results

    else:
        # we have a single date to render for, so nothing to aggregate!
        # just in case we check that there is no mismatch between the single day and the
        # argument containing specific weekdays restrictions if any
        if specific_weekdays == 'on_specific_weekdays':

            # we check if the date of the daterange matches the weekday(s) we target
            date = pd.Timestamp(query_dict['date'])

            if date.dayofweek in weekdays:
                query = prepare_sql_query(query_dict)
                query_results = make_sql_query(query, database)
                query_results_dict[query_dict['date']] = query_results

            else:
                print("The date selected does not match the weekday(s) indicated. Please select either an interval ('time_granularity': 'period') or a valid weekday(s) list.")

        else:
            query = prepare_sql_query(query_dict)
            query_results = make_sql_query(query, database)
            query_results_dict[query_dict['date']] = query_results

    return query_results_dict


def compute_min_max_passengers(trips_list, idx_weight):

    min_passenger_itinerary = min(trips_list, key=lambda x: x[idx_weight])
    max_passenger_itinerary = max(trips_list, key=lambda x: x[idx_weight])
    max_passenger = max_passenger_itinerary[idx_weight]
    min_passenger = min_passenger_itinerary[idx_weight]

    return min_passenger, max_passenger


def compute_weight(map_type, weight, max_passenger):
    # we normalise the weight of the point based on the max number of passengers
    # which means that from one day to another, although the biggest point will have the
    # same size, it will not represent the same number of passengers (compromise to
    # prevent having huge differences between the points, or squishing too much the scale
    # by using a log).

    if map_type != 'total':
        weight = weight/max_passenger*30
    else:
        weight = weight/max_passenger*20

    weight = int(weight)

    return weight


def render_frames(frame_dict):

    frames = []
    single_map = frame_dict['single_map']
    query_results_dict = frame_dict['query_results_dict']
    base_map = frame_dict['base_map']
    min_passenger = frame_dict['min_passenger']
    max_passenger = frame_dict['max_passenger']
    agg_per = frame_dict['agg_per']

    for query_date in query_results_dict:
        query_result = query_results_dict[query_date]
        for itinerary in query_result:
            zone_id_origin = Utils.convert_id_shape(itinerary[0])
            zone_id_destination = Utils.convert_id_shape(itinerary[1])
            if zone_id_origin == zone_id_destination:
                color = (141, 91, 67)
            else:
                color = (135, 162, 34)

            weight = compute_weight(single_map, itinerary[2], max_passenger)
            itinerary[2] = weight

            shape_origin = base_map.shape_dict[zone_id_origin]
            coords = shape_origin.center
            point_to_render = classfile.PointOnMap(coords, weight, color)
            itinerary[0] = point_to_render

            shape_dest = base_map.shape_dict[zone_id_destination]
            target_coords = shape_dest.center
            itinerary[1] = target_coords

        for frame in range(0, 60):
            map_rendered = base_map.map_file.copy()
            for itinerary in query_result:
                point_to_render = itinerary[0]
                target_coords = itinerary[1]
                if frame == 0:
                    point_to_render.render_point_on_map(map_rendered)
                else:
                    point_to_render.interpolate_next_position(target_coords, 60, frame)
                    point_to_render.render_point_on_map(map_rendered)
            date_info = (agg_per, query_date)
            display_specific_text_animation(map_rendered, date_info, single_map, min_passenger, max_passenger)
        frames.append(map_rendered)

    return frames


def make_video_animation(frames, image_size, map_type):

    # Build the title for the animation
    if map_type == 'total':
        title = 'Animation_{}.avi'.format('NYC')
    else:
        title = 'Animation_{}.avi'.format(map_type)

    animation = cv2.VideoWriter(title, cv2.VideoWriter_fourcc(*'DIVX'), 30, image_size)
    # video title, codec, fps, frame size

    for i in range(len(frames)):
        animation.write(frames[i])

    animation.release()


def display_specific_text_animation(rendered_frame, date_info, map_type, min_pass, max_pass):
    # note that these position are based on an image size of [1920, 1080]
    font = cv2.FONT_HERSHEY_SIMPLEX
    agg_per = date_info[0]
    date = date_info[1]

    # displays the date and the weekday, and if it is a special date
    if agg_per is False:
        cv2.putText(rendered_frame, date, (40, 150), font, 1.3, (221, 221, 221), 1, cv2.LINE_AA)

        special_dates_2018 = {'2018-01-01': 'New Year', '2018-12-25': 'Christmas', '2018-02-14': 'Valentine\'s Day', '2018-07-04': 'National Day', '2018-07-01': 'Hottest Day', '2018-01-07': 'Coldest Day'}
        if date in special_dates_2018:
            cv2.putText(rendered_frame, special_dates_2018[date], (40, 200), font, 1.3, (221, 221, 221), 1, cv2.LINE_AA)

        date_timestamp = pd.Timestamp(date)
        weekday = date_timestamp.dayofweek
        weekdays = {0: 'Monday', 1: 'Tuesday', 2: 'Wednesday', 3: 'Thursday', 4: 'Friday', 5: 'Saturday', 6: 'Sunday'}
        weekday = weekdays[weekday]
        cv2.putText(rendered_frame, weekday, (40, 95), font, 1.3, (221, 221, 221), 1, cv2.LINE_AA)

    else:
        cv2.putText(rendered_frame, 'Week of the {}'.format(date), (40, 150), font, 1.3, (221, 221, 221), 1, cv2.LINE_AA)

    # displays the legend of the colour code
    cv2.putText(rendered_frame, 'Origin and destination', (35, 260), font, 0.8, (255, 255, 255), 1, cv2.LINE_AA)
    cv2.circle(rendered_frame, (40, 290), 10, (141, 91, 67), -1)
    cv2.putText(rendered_frame, 'Identical', (60, 300), font, 0.6, (255, 255, 255), 1, cv2.LINE_AA)
    cv2.circle(rendered_frame, (40, 320), 10, (135, 162, 34), -1)
    cv2.putText(rendered_frame, 'Distinct', (60, 330), font, 0.6, (255, 255, 255), 1, cv2.LINE_AA)

    # displays the legend of the size of the circles
    cv2.putText(rendered_frame, 'Number of passengers', (35, 380), font, 0.8, (255, 255, 255), 1, cv2.LINE_AA)
    max_weight = compute_weight(map_type, max_pass, max_pass)
    cv2.circle(rendered_frame, (40, 420), max_weight, (255, 255, 255), 1)
    cv2.putText(rendered_frame, '{} passengers'.format(max_pass), (80, 420), font, 0.6, (255, 255, 255), 1, cv2.LINE_AA)
    min_weight = compute_weight(map_type, min_pass, max_pass)
    cv2.circle(rendered_frame, (40, 460), min_weight, (255, 255, 255), 1)
    cv2.putText(rendered_frame, '{} passenger'.format(min_pass), (80, 460), font, 0.6, (255, 255, 255), 1, cv2.LINE_AA)


def display_general_information_text(image, map_type, video_title):

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
        video_title = video_title + ' in ' + map_type

    # displays the title of the video
    # cv2.putText(image, video_title, (500, 1050), font, 1, (255, 255, 255), 2, cv2.LINE_AA)


# Main flow of the script

# shp_path = "/Users/acoullandreau/Desktop/Taxi_rides_DS/taxi_zones/taxi_zones.shp"

# animation_dict_2018 = {'image_size': (1920, 1080), 'margins': (),
#                       'maps_to_render': ['total', 'Manhattan', 'Bronx', 'Queens', 'Staten Island', 'Brooklyn'],
#                       'filter_on': [], 'zoom_on': [], 'filter_query_on_borough': False,
#                       'title': 'General flow of passengers in 2018',
#                       'db': 'nyc_taxi_rides', 'data_table': 'taxi_rides_2018',
#                       'lookup_table': 'taxi_zone_lookup_table', 'aggregated_result': 'count',
#                       'time_granularity': 'period', 'period':['2018-01-01', '2018-12-31'],
#                       'weekdays': (), 'aggregate_period': False}


animation_dict = {}
shp_path = input("Enter the path of the shapefile: ")
dict_input = input("Enter key and value separated by commas (,): ")

key, value = dict_input.split(",")
animation_dict[key] = value

image_size = animation_dict['image_size']
margin = animation_dict['margin']
maps_to_render = animation_dict['maps_to_render']
filter_on = animation_dict['filter_on']
zoom_on = animation_dict['zoom_on']
title = animation_dict['title']
database = animation_dict['db']
data_table = animation_dict['data_table']
lookup_table = animation_dict['lookup_table']
aggregated_result = animation_dict['aggregated_result']
filter_query_on_borough = animation_dict['filter_query_on_borough']
time_granularity = animation_dict['time_granularity']
period = animation_dict['period']
weekdays = animation_dict['weekdays']
aggregate_period = animation_dict['aggregate_period']

print('Building the base map...')

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
                 'title': title}
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
                     'zoom_on': zoom_on, 'map_type': single_map, 'title': title}

        base_map, projection = render_base_map(draw_dict)
        base_maps.append((single_map, base_map, projection))

# we define the render_animation_dict
render_animation_dict = {'time_granularity': time_granularity,
                         'period': period, 'weekdays': weekdays,
                         'filter_query_on_borough': filter_query_on_borough,
                         'database': database, 'data_table': data_table,
                         'lookup_table': lookup_table,
                         'aggregated_result': aggregated_result,
                         'aggregate_period': aggregate_period}

# we query the database
print('Querying the dabase...')

query_dict = build_query_dict(render_animation_dict)
render_animation_dict['query_dict'] = query_dict

print('Processing the query results...')
query_results_dict = process_query_arg(render_animation_dict)

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
