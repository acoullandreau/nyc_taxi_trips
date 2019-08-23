
import classfile
from utility import Utils

shp_path = "/Users/acoullandreau/Desktop/Taxi_rides_DS/taxi_zones/taxi_zones.shp"

animation_dict_2018 = {'image_size': (1920, 1080), 'margins': (), 
                       'maps_to_render': ['total', 'Manhattan', 'Bronx', 'Queens', 'Staten Island', 'Brooklyn'],
                       'filter_on': [], 'zoom_on': [], 'filter_query_on_borough': False,
                       'title': 'General flow of passengers in 2018',
                       'db': 'nyc_taxi_rides', 'data_table': 'taxi_rides_2018',
                       'lookup_table': 'taxi_zone_lookup_table', 'aggregated_result': 'count',
                       'time_granularity': 'period', 'period':['2018-01-01', '2018-12-31'],
                       'weekdays': (), 'aggregate_period': False}


animation_dict = {}
shp_path = input("Enter the path of the shapefile: ")
dict_input = input("Enter key and value separated by commas (,): ")

key, value = dict_input.split(",")
animation_dict[key] = value


def render_base_map(draw_dict):
    image_size = draw_dict['image_size']
    margins = draw_dict['margins']
    filter_on = draw_dict['filter_on']
    zoom_on = draw_dict['zoom_on']

    base_shapefile = classfile.ShapeFile(shp_path)
    base_shapefile.build_shape_dict(nyc_base_shapefile.df_sf)

    if filter_on != []:
        filter_cond = filter_on[0]
        filter_attr = filter_on[1]
        df_filtered = base_shapefile.filter_shape_to_render(filter_cond, filter_attr)
        base_shapefile.build_shape_dict(df_filtered)

    base_map = classfile.Map(base_shapefile, image_size)
    projection = classfile.Projection(base_map, margin)

    if zoom_on != []:
        zoom_on_cond = zoom_on[0]
        zoom_on_attr = zoom_on[1]
        zoom_shapefile = classfile.ShapeFile(shp_path)
        df_zoom = zoom_shapefile.filter_shape_to_render(zoom_on_cond, zoom_on_attr)
        zoom_shapefile.build_shape_dict(df_zoom)
        zoom_map = classfile.Map(zoom_shapefile, image_size)
        projection = classfile.Projection(zoom_map, margin)

    for zone_id in base_map.shape_dict:
        shape = base_map.shape_dict[zone_id]
        shape.project_shape_coords(projection)

    base_map.render_map()

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
        specific_weekdays = render_animation_dict['weekdays']
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


def make_sql_query(query):
    # connect to the database
    db = mysql.connector.connect(
        host="localhost",
        user="root",
        passwd="password",
        database=self.database
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



def make_flow_animation(animation_dict):
    # we extract the variables from the input dictionary
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
    if len(map_to_render) == 1:
        map_type = map_to_render[0]
        # we want to render on a single map
        draw_dict = {'image_size': image_size, 'margins': (), 'filter_on': [],
                     'zoom_on': []}
        base_map, projection = render_base_map(draw_dict)
        base_maps.append((map_type, base_map, projection))

    else:
        # we want to render multiple animations at once, for different base maps
        for single_map in map_to_render:
            zoom_on = [map_type, 'borough']
            draw_dict = {'image_size': image_size, 'margins': (), 'filter_on': [],
                         'zoom_on': []}

            base_map, projection = render_base_map(draw_dict)
            base_maps.append((map_type, base_map, projection))



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

    render_animation_dict['query_results_dict'] = query_results_dict
    render_animation_dict['min_passenger'] = min_passenger
    render_animation_dict['max_passenger'] = max_passenger

    # we render the animation!
    for map_type, base_map, projection in base_maps:
        # we add variabled to the render frame dictionary
        render_animation_dict['base_map'] = base_map
        render_animation_dict['projection'] = projection
        render_animation_dict['map_type'] = map_type

        render_animation_query_output(render_animation_dict)


def render_animation_query_output(render_animation_dict):

    # We extract the variables we will need from the input dictionary
    query_dict = render_animation_dict['query_dict']
    query_results_dict = render_animation_dict['query_results_dict']
    base_map = render_animation_dict['base_map']
    map_type = render_animation_dict['map_type']
    shape_dict = render_animation_dict['shape_dict']
    df_sf = render_animation_dict['df_sf']
    database = render_animation_dict['database']
    image_size = render_animation_dict['image_size']
    render_single_borough = render_animation_dict['render_single_borough']
    min_passenger = render_animation_dict['min_passenger']
    max_passenger = render_animation_dict['max_passenger']
    aggregate_period = render_animation_dict['aggregate_period']

    if query_dict['filter_query_on_borough'] is False:
        # in this case, we may want the base map to be reduced to map_type, but the query
        # to be performed on the whole city - thus we want to represent points that may
        # not be inside the shape of the reduced base map
        projection = render_animation_dict['projection']
        converted_shape_dict = convert_shape_boundaries(shape_dict, projection)

    else:
        # we isolate the set of zones we want to draw points for in the right coordinate system
        converted_shape_dict, projection = get_shape_set_to_draw(map_type, shape_dict, df_sf, image_size)

    # we build a dictionary for the details of the rendering of each frame
    render_frame_dict = {'database': database, 'min_passenger': min_passenger,
                         'max_passenger': max_passenger, 'base_map': base_map,
                         'converted_shape_dict': converted_shape_dict,
                         'map_type': map_type, 'frames': [], 'agg_per': aggregate_period}

    # we render frames depending on the results of the query and the period inputted
    for query_date in query_results_dict:
        render_frame_dict['query_date'] = query_date
        render_frame_dict['query_results'] = query_results_dict[query_date]
        frames = render_all_frames(render_frame_dict)
        render_frame_dict['frames'] = frames

    if map_type == 'total':
        print('Rendering the results for NYC...')
    else:
        print('Rendering the results for {}...'.format(map_type))

    # we compile the video from all frames
    make_video_animation(frames, image_size, map_type)

    if map_type == 'total':
        print('The video for NYC has been rendered')
    else:
        print('The video for {} has been rendered'.format(map_type))


def render_frame(frame, base_map, query_results, max_passenger, converted_shape_dict, map_type):

    # we make a copy of the map on which we will render the frame (each frame being
    # rendered on a new copy)
    map_rendered = base_map.copy()

    # we get each tuple from the query result, in the form (origin_id, dest_id, weight)
    for itinerary in query_results:
        zone_id_origin = convert_id_shape(itinerary[0])
        zone_id_destination = convert_id_shape(itinerary[1])

        weight = itinerary[2]
        weight = compute_weight(map_type, weight, max_passenger)

        # we get the coordinates of the center of the origin and the destination
        origin_coords = converted_shape_dict[zone_id_origin]['center']
        destination_coords = converted_shape_dict[zone_id_destination]['center']

        if frame == 0:
            # we start the rendering with the point at the origin
            # we convert to int as to be able to plot the point with opencv
            coords_point_to_draw = (int(origin_coords[0]), int(origin_coords[1]))

        else:
            # we extrapolate the position of the point between the origin and the
            # destination, as to have the point move from origin to destination
            # in 60 frames
            coords_point_to_draw = interpolate_next_position(origin_coords, destination_coords, 60, frame)

        x_point = coords_point_to_draw[0]
        y_point = coords_point_to_draw[1]

        if zone_id_origin == zone_id_destination:
            colour = (141, 91, 67)
        else:
            colour = (135, 162, 34)

        render_point_on_map(x_point, y_point, weight, map_rendered, colour)

    return map_rendered


def render_all_frames(render_frame_dict):

    # we extract the arguments we need from the input dictionary
    query_date = render_frame_dict['query_date']
    query_results = render_frame_dict['query_results']
    database = render_frame_dict['database']
    base_map = render_frame_dict['base_map']
    converted_shape_dict = render_frame_dict['converted_shape_dict']
    map_type = render_frame_dict['map_type']
    frames = render_frame_dict['frames']
    min_pass = render_frame_dict['min_passenger']
    max_pass = render_frame_dict['max_passenger']
    agg_per = render_frame_dict['agg_per']

    # we use the results of the query to render 60 frames
    # we want to render an animation of 1 second per given date, at 60 fps.
    for frame in range(0, 60):
        rendered_frame = render_frame(frame, base_map, query_results, max_pass, converted_shape_dict, map_type)

        # we display frame related text
        date_info = (agg_per, query_date)
        display_specific_text_animation(rendered_frame, date_info, map_type, min_pass, max_pass)

        frames.append(rendered_frame)

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





























def get_shape_set_to_draw(map_type, shape_dict, df_sf, image_size):

    # we define if we want to draw the whole map or only a borough (in this case map_type
    # should be the borough name)
    if map_type == 'total':
        shape_dict = shape_dict
    else:
        # we select the list of zone_id we want to draw that belong only to the targeted
        # borough to draw
        shape_dict = reduce_shape_dict_to_borough(shape_dict, df_sf, map_type)

    # We define the projection parameters to be able to convert the coordinates into
    # the image scale coordinate system
    # we convert the coordinates of the shapes to draw
    map_max_bound, map_min_bound = find_max_coords(shape_dict)
    projection = define_projection(map_max_bound, map_min_bound, image_size)
    converted_shape_dict = convert_shape_boundaries(shape_dict, projection)

    return converted_shape_dict, projection


def reduce_shape_dict_to_borough(shape_dict, df_sf, borough_name):

    borough_df = df_sf[df_sf['borough'] == borough_name]
    borough_id = []
    for objectid in borough_df.index:
        borough_id.append(objectid)

    reduced_shape_dict = {}
    # we add to the reduced_shape_dict only the zones belonging to the borough area targeted
    for zone_id in borough_id:
        reduced_shape_dict[zone_id] = shape_dict[zone_id]

    return reduced_shape_dict


def interpolate_next_position(origin_coords, destination_coords, tot_frames, curr_frame):

    # as to perform the arithmetic operations, we convert everything to float for more
    # precision
    x_origin = float(origin_coords[0])
    y_origin = float(origin_coords[1])
    x_destination = float(destination_coords[0])
    y_destination = float(destination_coords[1])
    tot_frames = float(tot_frames - 1)
    curr_frame = float(curr_frame)

    delta_x = (x_destination - x_origin)/tot_frames
    delta_y = (y_destination - y_origin)/tot_frames

    # the rendering with OpenCV demands integers values for the positioning, so we convert
    # w and y to int
    new_x = int(x_origin+delta_x*curr_frame)
    new_y = int(y_origin+delta_y*curr_frame)

    return new_x, new_y





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


def display_specific_text_animation(rendered_frame, date_info, map_type, min_pass, max_pass):
    # note that these position are based on an image size of [1920, 1080]
    font = 
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

    def apply_project_to_shape_dict(self):

        proj = self.projection
        axis_to_center = proj['axis_to_center']
        image_x_max = proj['image_size'][0]
        image_y_max = proj['image_size'][1]
        map_x_max = proj['map_max_bound'][0]
        map_y_max = proj['map_max_bound'][1]
        map_max_converted = (self.apply_projection(map_x_max, map_y_max, proj))
        map_x_min = proj['map_min_bound'][0]
        map_y_min = proj['map_min_bound'][1]
        map_min_converted = (self.apply_projection(map_x_min, map_y_min, proj))

        if axis_to_center == 'x':
            map_x_max_conv = map_max_converted[0]
            map_x_min_conv = map_min_converted[0]
            center_translation = (image_x_max - (map_x_max_conv - map_x_min_conv))/2
        else:
            map_y_max_conv = map_max_converted[1]
            map_y_min_conv = map_min_converted[1]
            center_translation = (image_y_max - (map_y_max_conv - map_y_min_conv))/2

        for zone_id in self.shape_dict:
            curr_shape = self.shape_dict[zone_id]

            points = curr_shape['points']
            x_center = curr_shape['center'][0]
            y_center = curr_shape['center'][1]
            max_bound = curr_shape['max_bound']
            min_bound = curr_shape['min_bound']

            converted_points = []
            for point in points:
                # we convert the coordinates to the new coordinate system
                conv_point = [0, 0]
                conv_point[0], conv_point[1] = self.apply_projection(point[0], point[1], proj)
                # we center the map on the axis that was not used to scale the image
                if axis_to_center == 'x':
                    conv_point[0] = conv_point[0] + center_translation
                else:
                    conv_point[1] = conv_point[1] + center_translation

                # we mirror the image to match the axis alignment
                conv_point[1] = image_y_max - conv_point[1]
                converted_points.append(conv_point)

            # we convert the center and the max and min boundaries
            x_center, y_center = Utils.calculate_centroid(converted_points)
            max_bound = (self.apply_projection(max_bound[0], max_bound[1], proj))
            min_bound = (self.apply_projection(min_bound[0], min_bound[1], proj))

            # We edit the dictionary with the new coordinates
            self.shape_dict[zone_id] = {}
            self.shape_dict[zone_id]['points'] = converted_points
            self.shape_dict[zone_id]['center'] = (x_center, y_center)
            self.shape_dict[zone_id]['max_bound'] = max_bound
            self.shape_dict[zone_id]['min_bound'] = min_bound







