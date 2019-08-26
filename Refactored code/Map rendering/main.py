import cv2
import json
import numpy as np
import pandas as pd

import classfile
from utility import Utils


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
    if time_granularity == 'specific_weekdays' or weekdays != []:
        query_dict['specific_weekdays'] = 'on_specific_weekdays'

    # used specifically for the animation logic
    elif time_granularity == 'period':
        query_dict['specific_weekdays'] = False

    # used specifically for the heat_map logic
    elif time_granularity == 'weekdays_vs_weekends':
        query_dict['specific_weekdays'] = 'weekdays_vs_weekends'

    return query_dict


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

    # displays the title
    # cv2.putText(image, title, (500, 1050), font, 1, (255, 255, 255), 2, cv2.LINE_AA)


def display_scale_legend(map_image, font, min_pass, max_pass, colors):
    # we dynamically print a legend using a fixed step between two colors plotted

    k = 0
    top_bar_x = 30
    top_bar_y = 440

    # we add a legend for no passengers traveling
    cv2.rectangle(map_image, (top_bar_x, top_bar_y), (top_bar_x+40, top_bar_y + 20), (255, 255, 255), 1)
    cv2.putText(map_image, 'No flow of people', (top_bar_x + 70, top_bar_y + 15), font, 0.7, (221, 221, 221), 1, cv2.LINE_AA)
    top_bar_y = top_bar_y + 22

    # we prepare the ground to plot a dynamic legend for the colors
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
        k += 1

    # we check if there are negative and positive values to represent and if we already
    # have a 0 to represent ; if not, we will add it to the list of steps to plot
    neg_value_count = 0
    pos_value_count = 0
    zero_count = 0
    for level in levels:
        if level < 0:
            neg_value_count += 1
        elif level == 0:
            zero_count += 1
        else:
            pos_value_count += 1

    if zero_count == 0:
        if neg_value_count > 0 and pos_value_count > 0:
            levels.append(0)

    # we plot dynamically the legend
    levels.sort()
    for level in levels:
        color = compute_color(level, min_pass, max_pass)
        level = "{0:.2f}".format(level)
        cv2.rectangle(map_image, (top_bar_x, top_bar_y), (top_bar_x+40, top_bar_y + 20), color, -1)
        if float(level) == 0 or abs(float(level)) == 1:
            cv2.putText(map_image, '{} passenger'.format(level), (top_bar_x + 70, top_bar_y + 15), font, 0.7, (221, 221, 221), 1, cv2.LINE_AA)
        else:
            cv2.putText(map_image, '{} passengers'.format(level), (top_bar_x + 70, top_bar_y + 15), font, 0.7, (221, 221, 221), 1, cv2.LINE_AA)
        top_bar_y = top_bar_y + 20


def display_specific_text(map_image, zone_id, zone_name, flow_dir, min_pass, max_pass, colors):

    # note that these position are based on an image size of [1920, 1080]
    font = cv2.FONT_HERSHEY_SIMPLEX

    # display the zone id and name
    cv2.putText(map_image, '({})'.format(flow_dir), (30, 170), font, 1.3, (221, 221, 221), 1, cv2.LINE_AA)
    cv2.putText(map_image, '{} - '.format(zone_id), (30, 240), font, 1.3, (221, 221, 221), 1, cv2.LINE_AA)
    cv2.putText(map_image, '{}'.format(zone_name), (220, 240), font, 1.3, (221, 221, 221), 1, cv2.LINE_AA)

    # displays the legend of the colour code
    cv2.putText(map_image, 'Legend', (30,320), font, 0.9, (221, 221, 221), 1, cv2.LINE_AA)
    cv2.rectangle(map_image,(30,340),(70,360),(95, 240, 255),3)
    cv2.putText(map_image, 'Target zone', (100, 360), font, 0.7, (221, 221, 221), 1, cv2.LINE_AA)
    cv2.putText(map_image, 'Average number of passengers', (30, 410), font, 0.7, (221, 221, 221), 1, cv2.LINE_AA)
    cv2.putText(map_image, '* A negative value means more flow on weekends', (30, 430), font, 0.5, (221, 221, 221), 1, cv2.LINE_AA)

    display_scale_legend(map_image, font, min_pass, max_pass, colors)


def find_names(zone_shape, base_map):

    df_sf = base_map.shapefile.df_sf
    zone_id = zone_shape.shape_id

    zone_name = df_sf[df_sf.index == zone_id]['zone'].item()
    # borough_name = df_sf[df_sf.index == zone_id]['borough'].item()

    return zone_name


def parse_shapefile(shp_path):
    base_shapefile = classfile.ShapeFile(shp_path)
    base_shapefile.build_shape_dict(base_shapefile.df_sf)

    return base_shapefile


def prepare_sql_query(query_dict):

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


def process_query_results(query_results, base_map):

    in_shape_ids = []
    incoming_flow = {}
    out_shape_ids = []
    outgoing_flow = {}

    for itinerary in query_results:
        origin_id = Utils.convert_id(itinerary[0])
        destination_id = Utils.convert_id(itinerary[1])
        weight = itinerary[2]
        origin_ids = []
        destination_ids = []
        # we look only at shapes that are to be rendered
        if origin_id in base_map.shape_dict or destination_id in base_map.shape_dict:
            shape_origin = base_map.shape_dict[origin_id]
            origin_ids.append(origin_id)
            shape_destination = base_map.shape_dict[destination_id]
            destination_ids.append(destination_id)

        # We build a dictionary of outgoing traffic
        for origin_id in origin_ids:
            if origin_id not in out_shape_ids:
                out_shape_ids.append(origin_id)
                outgoing_flow[shape_origin] = []
            outgoing_flow[shape_origin].append((shape_destination, weight))
        # We build a dictionary of incoming traffic
        for destination_id in destination_ids:
            if destination_id not in in_shape_ids:
                in_shape_ids.append(destination_id)
                incoming_flow[shape_destination] = []
            incoming_flow[shape_destination].append((shape_origin, weight))

    return outgoing_flow, incoming_flow


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

    if filter_on:
        filter_cond = filter_on[0]
        filter_attr = filter_on[1]
        df_filtered = base_shapefile.filter_shape_to_render(filter_cond, filter_attr)
        base_map.shape_dict_filt = base_map.build_shape_dict(df_filtered)

    if zoom_on != []:
        zoom_on_cond = zoom_on[0]
        zoom_on_attr = zoom_on[1]
        zoom_shapefile = classfile.ShapeFile(shp_path)
        df_zoom = zoom_shapefile.filter_shape_to_render(zoom_on_cond, zoom_on_attr)
        zoom_shapefile.build_shape_dict(df_zoom)
        zoom_shapefile.df_sf = df_zoom
        zoom_map = classfile.Map(zoom_shapefile, image_size)
        projection = classfile.Projection(zoom_map, margins)

    base_map.projection = projection
    for zone_id in base_map.shape_dict_filt:
        shape = base_map.shape_dict_filt[zone_id]
        shape.project_shape_coords(base_map.projection)

    for zone_id in base_map.shape_dict:
        shape = base_map.shape_dict[zone_id]
        shape.project_shape_coords(base_map.projection)

    base_map.render_map()
    display_general_information_text(base_map.map_file, map_type, title)

    return base_map, projection


def render_single_map(flow_dict, flow_dir, base_map, file_name, zone_shape):

    map_rendered = base_map.map_file.copy()
    zone_name = find_names(zone_shape, base_map)
    zone_id = Utils.convert_id(zone_shape.shape_id, inverse=True)
    map_title = '{}_{}_{}_{}_{}'.format(file_name[0], zone_id, zone_name,
                                        flow_dir, file_name[1])
    trips_list = flow_dict[zone_shape]
    min_passenger, max_passenger = Utils.compute_min_max_passengers(trips_list, 1)

    colors = []
    for linked_zone in trips_list:
        shape_to_color = linked_zone[0]
        if shape_to_color.shape_id != zone_shape.shape_id:
            weight = linked_zone[1]
            render_color = compute_color(weight, min_passenger, max_passenger)
            shape_to_color.color_fill = render_color
            if render_color not in colors:
                colors.append(render_color)
            shape_to_color.fill_in_shape(map_rendered)
            # we draw again the boundaries of the shape after filling it in
            pts = np.array(shape_to_color.points, np.int32)
            cv2.polylines(map_rendered, [pts], True, (255, 255, 255), 1, cv2.LINE_AA)

    # outline the focused shape
    zone_shape.color_line = [95, 240, 255]
    zone_shape.line_thick = 3
    pts = np.array(zone_shape.points, np.int32)
    cv2.polylines(map_rendered, [pts], True, zone_shape.color_line, zone_shape.line_thick, cv2.LINE_AA)
    # display the legend
    display_specific_text(map_rendered, zone_id, zone_name, flow_dir, min_passenger, max_passenger, colors)

    # save the image
    cv2.imwrite(('{}.png').format(map_title), map_rendered)


def render_maps(flow_dict, flow_dir, base_map, file_name, focus_dict):

    if focus_dict != {}:
        for zone_shape in flow_dict:
            if zone_shape.shape_id in focus_dict:
                render_single_map(flow_dict, flow_dir, base_map, file_name, zone_shape)
    else:
        for zone_shape in flow_dict:
            render_single_map(flow_dict, flow_dir, base_map, file_name, zone_shape)


# Main flow of the script

with open('conf.json', encoding='utf-8') as config_file:
    conf_data = json.load(config_file)

shp_path = conf_data['shp_path']
image_size = conf_data['image_size']

if conf_data['margins']:
    margins = conf_data['margins']
else:
    margins = [0, 0, 0, 0]

maps_to_render = conf_data['maps_to_render']
filter_on = conf_data['filter_on']
zoom_on = conf_data['zoom_on']
focus_on = conf_data['focus_on']
title = conf_data['title']
database = conf_data['db']
data_table = conf_data['data_table']
lookup_table = conf_data['lookup_table']
aggregated_result = conf_data['aggregated_result']
filter_query_on_borough = conf_data['filter_query_on_borough']
period = conf_data['period']
weekdays_vs_weekends = conf_data['weekdays_vs_weekends']

if weekdays_vs_weekends is True:
    time_granularity = 'weekdays_vs_weekends'
else:
    time_granularity = 'period'

print('Building the base map...')

# Parse the shapefile
base_shapefile = parse_shapefile(shp_path)

focus_dict = {}
if focus_on:
    focus_cond = focus_on[0]
    focus_attr = focus_on[1]
    focus_df = base_shapefile.filter_shape_to_render(focus_cond, focus_attr)
    focus_dict = base_shapefile.build_shape_dict(focus_df)

# Draw the base map and keep it in a saved variable
base_maps = []

if len(maps_to_render) == 1:
    if maps_to_render[0] == 'total':
        zoom_on = []
    else:
        zoom_on = [maps_to_render[0], 'borough']

    # we want to render on a single map
    draw_dict = {'image_size': image_size, 'margins': margins, 'filter_on': filter_on,
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
        draw_dict = {'image_size': image_size, 'margins': margins, 'filter_on': filter_on,
                     'zoom_on': zoom_on, 'map_type': single_map,
                     'title': title, 'base_shapefile': base_shapefile}

        base_map, projection = render_base_map(draw_dict)
        base_maps.append((single_map, base_map, projection))

# we build the query statement and execute it on the database
print('Querying the dabase...')
# we define the render_heat_map_dict
render_heat_map_dict = {'time_granularity': time_granularity, 'period': period,
                        'image_size': image_size, 'data_table': data_table,
                        'lookup_table': lookup_table, 'aggregated_result': aggregated_result,
                        'title': title, 'filter_query_on_borough': filter_query_on_borough,
                        'weekdays': [], 'aggregate_period': False}

query_dict = build_query_dict(render_heat_map_dict)

if query_dict['date'] == 'loop_through_period':
    # if we have the flag loop_through_period in the query dict, it means the period
    # set for the query is multiple dates, therefore we want the query to return an
    # average on a time interval, and not on a single date
    period = render_heat_map_dict['period']
    daterange = pd.date_range(period[0],period[1])
    query_dict['date'] = period

query = prepare_sql_query(query_dict)
query_results = Utils.make_sql_query(query, database)

for single_map, base_map, projection in base_maps:
    # we process the query results
    outgoing_flow, incoming_flow = process_query_results(query_results,
                                                         base_map)
    print('Rendering {}...'.format(single_map))
    if single_map == 'total':
        if time_granularity == 'weekdays_vs_weekends':
            file_name = ['NYC', '2018_diff_WD_WE']
        else:
            file_name = ['NYC', '2018']
    else:
        if time_granularity == 'weekdays_vs_weekends':
            file_name = ['{}'.format(single_map), '2018_diff_WD_WE']
        else:
            file_name = ['{}'.format(single_map), '2018']

    print('Rendering {} outgoing flow...'.format(single_map))
    render_maps(outgoing_flow, 'out', base_map, file_name, focus_dict)
    print('Rendering {} incoming flow...'.format(single_map))
    render_maps(incoming_flow, 'in', base_map, file_name, focus_dict)

    print('Chloropleth maps for {} rendered.'.format(single_map))
