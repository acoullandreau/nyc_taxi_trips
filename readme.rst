=========================================
Taxi rides analysis - code documentation
=========================================


-----------------------
Purpose of this project
-----------------------

| As part of the UDACITY Data Scientist Nanodegree, I was asked to choose a dataset, choose three questions to answer to, and write a blog post to communicate my conclusions.
| I chose to work with a portion of the TLC Trip Record Data - the yellow taxi trips of 2018 (about 99 million rows). The full dataset is available on the TLC Trip Record Data page (https://www1.nyc.gov/site/tlc/about/tlc-trip-record-data.page).

| I wanted to conduct my analysis from the point of view of an urban planner - where are people going, and what are the trends of the flow of passengers?
| I chose to look closer at the dataset in order to answer the following questions:

- Can we see trends in the flow of passengers in 2018?
- Is there a difference on holidays, hottest or coldest day of the year?
- Is there a difference between weekdays and weekends?
- Depending on the zone we look at, where are people most likely to come from? To go to? Is it different between weekdays and weekends?


In this repository, you will find:

- A Jupyter notebook (Taxi rides analysis) exposing the first approach I took, using static visualisations
- A second Jupyter notebook (Taxi rides analysis II) with the second approach using a database and OpenCV to render animations and heat maps
- The few animations that were generated (using arguments provided in the second notebook)
- The few heat maps generated (likewise)
- A code flow graph to expose the connections of the functions for the animation rendering
- A code flow graph to expose the connections of the functions for the heat map rendering
- This readme file containing documentation of the functions, as well as the installation requisites and sources


Note that two blog posts were written to expose the conclusions and the process of the analysis, and can be found here:

- XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
- XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX

Important note: in the code and documentation below, we talk about a heat map, while the representation we use is actually called a **choropleth map**.


-----------------------
Installation requisites
-----------------------

| To document the code, I used Jupyter notebook 6.0.0.
| The code is written in Python 3 (v3.6).
| The database's version is MariaDB (5.7.18). 


The following libraries were used extensively in the code:

- numpy 1.16.4
- pandas 0.25.0
- shapefile (pyshp) 2.1.0
- pyproj 1.9.6
- matplotlib 3.1.0
- OpenCV 4.1.0
- mysql-connector-python 8.0.16
- cmapy 0.5



------------------
Code documentation
------------------

This section will focus on the second approach (database and animation or heat map rendering), as it is more complex and easier to reuse. 
The code of the first approach (using matplotlib and loading the data as a dataframe into the notebook) is already documented in the first notebook.
Note that the process of switching from one approach to the other is documented in this blog post : XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX


Database set up
---------------

Here are the SQL queries used to load a csv file in which all the files of a single year were merged.

| #Create a table with all columns and indexes
|	CREATE TABLE taxi_rides_2017 (
	|	id INT NOT NULL AUTO_INCREMENT FIRST,
	|	VendorID INTEGER NOT NULL,
	|	tpep_pickup_datetime TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
	|	tpep_dropoff_datetime TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
	|	pickup_date DATE NULL,
	|	pickup_weekday INTEGER NOT NULL,
	|	dropoff_date DATE NULL,
	|	dropoff_weekday INTEGER NOT NULL,
	|	passenger_count INTEGER NULL,
	|	trip_distance FLOAT NULL,
	|	RatecodeID INTEGER NOT NULL,
	|	store_and_fwd_flag CHARACTER(1) NOT NULL,
	|	PULocationID INTEGER NOT NULL,
	|	DOLocationID INTEGER NOT NULL,
	|	payment_type INTEGER NOT NULL,
	|	fare_amount FLOAT NULL,
	|	extra FLOAT NULL,
	|	mta_tax FLOAT NULL,
	|	tip_amount FLOAT NULL,
	|	tolls_amount FLOAT NULL,
	|	improvement_surcharge FLOAT NULL,
	|	total_amount FLOAT NULL,
	|	PRIMARY KEY (id),
	|	INDEX pickup_date (pickup_date),
	|	INDEX pickup_weekday (pickup_weekday),
	|	INDEX dropoff_date (dropoff_date),
	|	INDEX dropoff_weekday (dropoff_weekday),
	|	FOREIGN KEY (PULocationID) REFERENCES taxi_zone_lookup_table(LocationID),
	|	FOREIGN KEY (DOLocationID) REFERENCES taxi_zone_lookup_table(LocationID)
	|	);

|#Load the data - merged file for a year
|	LOAD DATA LOCAL INFILE '/Users/acoullandreau/Desktop/Taxi_rides_DS/2017/merged_2017.csv' 
|	INTO TABLE taxi_rides_2017 
|	FIELDS TERMINATED BY ',' 
|	LINES TERMINATED BY '\r\n'
|	IGNORE 1 ROWS#Ignore header
|	(VendorID,tpep_pickup_datetime,tpep_dropoff_datetime, passenger_count, trip_distance, RatecodeID, store_and_fwd_flag, PULocationID,	DOLocationID, payment_type, fare_amount, extra, mta_tax, tip_amount, tolls_amount, improvement_surcharge, 	total_amount) 
|	SET id=null,#sets ID to auto-increment
|	pickup_date = DATE(tpep_pickup_datetime),
|	pickup_weekday = WEEKDAY(tpep_pickup_datetime), 
|	dropoff_date = DATE(tpep_dropoff_datetime), 
|	dropoff_weekday = WEEKDAY(tpep_dropoff_datetime)
	;

|#Clean up the data
|	DELETE FROM nyc_taxi_rides.taxi_rides_2017 
|	WHERE PULocationID IN (0, 264, 265) 
|	OR DOLocationID IN (0, 264, 265) 
|	OR passenger_count  = 0 
|	OR tpep_pickup_datetime = 0 
|	OR tpep_dropoff_datetime  = 0 
|	OR fare_amount <0 
|	OR extra<0 
|	OR mta_tax<0 
|	OR tip_amount<0 
|	OR tolls_amount<0 
|	OR improvement_surcharge<0;



For the rendering of the heat maps, we chose to create another table in the database, with preprocessed results. As a matter of fact, the query to compute the difference of the average on a given period between the weekdays and weekends numbers of passengers was going to be pushy. In order to speed up calculation time, we create another table in the database, called passenger_count_2018, that contains for each day and each link (grouped from origin PULocationID to destination DOLocationID) the total number of passengers.

|CREATE TABLE passenger_count_2018 (
|	id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
|	pickup_date DATE NULL,
|    pickup_weekday INTEGER NOT NULL,
|    passenger_count_per_day FLOAT NULL,
|	PULocationID INTEGER NOT NULL,
|	DOLocationID INTEGER NOT NULL,
|	INDEX pickup_date (pickup_date),
|	INDEX pickup_weekday (pickup_weekday),
|	FOREIGN KEY (PULocationID) REFERENCES taxi_zone_lookup_table(LocationID),
|	FOREIGN KEY (DOLocationID) REFERENCES taxi_zone_lookup_table(LocationID)
|	);

| INSERT INTO passenger_count_2018 (pickup_date, pickup_weekday, passenger_count_per_day, PULocationID, DOLocationID) 
| SELECT pickup_date, pickup_weekday, COUNT(passenger_count), PULocationID, DOLocationID
| FROM taxi_rides_2018
| WHERE pickup_date BETWEEN '2018-01-01 00:00:00' AND '2018-12-31 23:59:59'
| GROUP BY PULocationID, DOLocationID, pickup_date, pickup_weekday;


|As for the query associated with the computation of the difference between weekdays and weekends, here is a focus on the logic. 
|The table we want to query is an intermediate, pre-processed table, that already contains the count of passengers per link per day. The idea of using preprocessed data, as well as having both the date and the weekday used as indexes, is to speed up the calculation.
|And indeed, we need it when it comes to compute the difference in the number of passengers between weekdays and weekends, because we need to join several tables.

The query works as follow:

- we left join a table extracting only weekdays count of people with a table extracting only weekends count of people. With this table, we might have rows from the weekends table that contains only NULL values, so we will want to replace them with the PULocationID and DOLocationID of the weekdays table, and 0 as a count of people.
- we right join a table extracting only weekdays count of people with a table extracting only weekends count of people. With this table, we might have rows from the weekdays table that contains only NULL values, so we will want to replace them with the PULocationID and DOLocationID of the weekends table, and 0 as a count of people.
- we union these two tables, and use CASE statements to replace the NULL values we gathered from the joins. We then have the PULocationID and DOLocationID of both the weekdays and weekends that are the same, and some 0 values for the counts of people.
- we select only one PULocationID column, one DOLocationID column, and compute the difference in the counts of people.

If needed, we add a statement to join the lookup table in order to filter per borough.

Here is the query:

|SELECT wd_pu_id pu_id, wd_do_id do_id, wd_aggregated_result - we_aggregated_result diff
|FROM(SELECT CASE WHEN wd_pu_id IS NULL THEN we_pu_id ELSE wd_pu_id END AS wd_pu_id, 
|				CASE WHEN wd_do_id IS NULL THEN we_do_id ELSE wd_do_id END AS wd_do_id,
|				CASE WHEN wd_aggregated_result IS NULL THEN 0 ELSE wd_aggregated_result END AS wd_aggregated_result,
|				CASE WHEN we_pu_id IS NULL THEN wd_pu_id ELSE we_pu_id END AS we_pu_id, 
|				CASE WHEN we_do_id IS NULL THEN wd_do_id ELSE we_do_id END AS we_do_id,
|				CASE WHEN we_aggregated_result IS NULL THEN 0 ELSE we_aggregated_result END AS we_aggregated_result
|FROM (SELECT *
|	FROM (SELECT PULocationID wd_pu_id, DOLocationID wd_do_id, COUNT(passenger_count_per_day) wd_aggregated_result
|			FROM passenger_count_2018
|			WHERE pickup_date BETWEEN '2018-01-01' AND '2018-01-07' AND pickup_weekday IN (0, 1, 2, 3, 4) 
|			GROUP BY wd_pu_id, wd_do_id) as weekdays
|	LEFT JOIN (SELECT PULocationID we_pu_id, DOLocationID we_do_id, COUNT(passenger_count_per_day) we_aggregated_result
|			FROM passenger_count_2018
|			WHERE pickup_date BETWEEN '2018-01-01' AND '2018-01-07' AND pickup_weekday IN (5, 6) 
|			GROUP BY we_pu_id, we_do_id) as weekends
|	ON weekdays.wd_pu_id = weekends.we_pu_id AND weekdays.wd_do_id = weekends.we_do_id
|	UNION 
|   SELECT *
|	FROM (SELECT PULocationID wd_pu_id, DOLocationID wd_do_id, COUNT(passenger_count_per_day) wd_aggregated_result
|			FROM passenger_count_2018
|			WHERE pickup_date BETWEEN '2018-01-01' AND '2018-01-07' AND pickup_weekday IN (0, 1, 2, 3, 4) 
|			GROUP BY wd_pu_id, wd_do_id) as weekdays
|	RIGHT JOIN (SELECT PULocationID we_pu_id, DOLocationID we_do_id, COUNT(passenger_count_per_day) we_aggregated_result
|			FROM passenger_count_2018
|			WHERE pickup_date BETWEEN '2018-01-01' AND '2018-01-07' AND pickup_weekday IN (5, 6) 
|			GROUP BY we_pu_id, we_do_id) as weekends
|	ON weekdays.wd_pu_id = weekends.we_pu_id AND weekdays.wd_do_id = weekends.we_do_id) as table_1) as table_2;



The flow of the code - animation rendering
------------------------------------------

| First of all, the script takes as an input a dictionary with the set of parameters used to determine what to render. The details on what this dictionary should contain is **provided in the next sub-section**.
| All arguments are used by the script (make_flow_animation) to call the functions that will perform the rendering operations.

| The first functions call **process the shapefile** (shp_to_df and process_shape_boundaries). 
| Then comes the **drawing of the base map**. The main function (draw_base_map) receives a dictionary as an input, and returns both the base map (image object) and the projection used to scale the objects rendered on the image. 
| draw_dict = {'image_size':image_size, 'render_single_borough':render_single_borough,
|              'map_type':map_type, 'title':title, 
|              'shape_dict':shape_boundaries, 'df_sf':df_sf}


| The script finally calls the function in charge of **processing and rendering the animation** (render_animation_query_output). It also accepts a dictionary as an input.
| render_animation_dict = {'time_granularity':time_granularity, 'period':period,  
|                          'weekdays':weekdays,'base_map':base_map,
|                          'filter_query_on_borough':filter_query_on_borough, 
|                          'projection':projection, 'map_type':map_type,
|                          'image_size':image_size,'shape_dict':shape_boundaries, 
|                          'df_sf':df_sf,'database':database, 'data_table':data_table, 
|                          'lookup_table':lookup_table,
|                          'aggregated_result':aggregated_result,
|                          'render_single_borough':render_single_borough,
|                          'video_title':title}

This function (render_animation_query_output) is actually in charge of three things:

- build the query
- render each frame
- build one or more videos with all the frames rendered

| To build the query, the function (build_query_dict) is called, and is passed a dictionary as an argument.
| query_dict = {'data_table':'taxi_rides_2018', 'lookup_table':'taxi_zone_lookup_table', 
|              'aggregated_result':'avg', 'date':single_date, 
|              'specific_weekdays':'on_specific_weekdays', 'filter_query_on_borough':'Manhattan'}

For simplification, as the number of passengers that travel *between two days* (i.e leave one day and arrive the next, because they	travel around midnight) is negligeable compared to the rest of the trips, we **use the pick up date as a reference for the date**.

| Using this query_dict obtained, the rendering of each frame is taken care of by the (render_all_frames) function. This function also uses a dictionary as an input.
| render_frame_dict = {'query_dict':query_dict, 'database':database,
|                      'base_map':base_map, 'converted_shape_dict': converted_shape_dict,
|                      'map_type':map_type, 'frames': frames,
|                      'video_title': title}

This function (render_all_frames) takes care of:

- querying the database, using prepare_sql_query and make_sql_query, that returns the result of the query
- rendering each frame, using render_frame, that returns an image object, after calculating the position and rendering the points on a copy of the base map
- appending each frame to a list of all frames, that will be used to build the animation (by the render_animation_query_output function).


| A graph is provided in this repository with the logical flow of the code.
| Note that other support functions are used and not mentioned here but included in the graph and the documentation below.
 

The flow of the code - heat map rendering
------------------------------------------

This function, overall, will follow pretty much the same flow, to the exception that it is not as flexible regarding the maps we render - by default, we will render all of them. Which means that upon lauching the script, we will see as an output:

- one map per zone showing the whole city with incoming flow
- one map per zone showing the whole city with outgoing flow
- one map per zone focused on the borough the zone belongs to with incoming flow
- one map per zone focused on the borough the zone belongs to with outgoing flow


| What we choose, however, is whether we want to represent the count or average of passengers on the whole year, or a difference between weekdays and weekends flows. 
| Likewise, the script takes as an input a dictionary with the set of parameters used to determine what to render. The details on what this dictionary should contain is **provided in the next sub-section**.
| All arguments are used by the script (make_heat_map) to call the functions that will perform the rendering operations.


The logic is similar to the one of the animation rendering, though not exactly the same:

- process the shapefile
- build the query
- execute the query
- process the query results (split to incoming and outgoing dictionaries)
- for each zone id, render two maps (whole city and borough focused) for incoming flow
- for each zone id, render two maps (whole city and borough focused) for outgoing flow


| The first functions call **process the shapefile** (shp_to_df and process_shape_boundaries). We store the results of this first processing step in a dictionary (render_heat_map_dict) that will be used as an input to render the maps.
| The script then calls the functions to **build the query, execute the query and process the results**. The output of these functions are also added to the render_heat_map_dict. 
| Finally, the (render_heat_map_query_output) function is called twice, once for the incoming flow and once for the outgoing flow.

This last function (render_heat_map_query_output) is provided a dictionary for each flow direction. This dictionary is built using the zone_id as a key, and a list of tuples as a value. The list of tuples contains the id of the zone 'linked' to the key zone id and the weight (number of passengers) of that link. So basically, in the incoming dictionary we have as a key the zone_idof the zones where people *go to*, and as a list the zone id of where they come from and how many people went. For example, for a given period, n passengers went to zone A coming from zone B, m passengers coming from zone C. The dictionary will look like this:
| incoming_dict = {'A';[(B, n), (C,m)]}

The logic is the same for the outgoing flow, except that the tuple now contains the zone_id of the zones where people *go* while coming from the key zone. 

The function (render_heat_map_query_output) will loop through the keys of either dictionary, and for each zone execute the following actions:

- associate to the zone_id a zone name and a borough name
- build the file name that will be used to save the output map image
- render the map for the whole city
- render the map borough focused

| The last two steps are performed using yet another function called (render_map), that also accepts a dictionary as an input:
| render_map_dict_borough = {'map_to_render':borough_name, 'zone_id': zone_id, 
|                          	'trips_list':trips_list, 'draw_dict':draw_dict,
|                          	'file_name':borough_file_name}
 

To render the map using the (render_map), the following steps are performed:

- draw the base map (using the same function than for the animation)
- build the dictionary of shape boundaries (using the same function than for the animation)
- highlight the zone we are drawing the maps for
- color the shapes of the zones linked to it (either from where passengers are coming, or where they are going to)
- add the legend and other informational text
- save the image using the file name


A graph is provided in this repository with the logical flow of the code.
Note that other support functions are used and not mentioned here but included in the graph and the documentation below. 
 


Main script input
-----------------

**To render animations:**

| animation_dict = {'shp_path':shp_path, 'image_size':(1920,1080), 'map_to_render':['total', 'Manhattan'],
|					'render_single_borough':False, 'filter_query_on_borough':False, 
|					'title':'General flow of passengers in 2018', 'db':'nyc_taxi_rides', 
| 					'data_table':'taxi_rides_2018', 'lookup_table':'taxi_zone_lookup_table', 
|					'aggregated_result':'count', 'time_granularity':'period', 
| 					'period':['2018-01-01','2018-01-03'], 'weekdays':[]}


Arguments:

- shp_path: the path to the shapefile used to render the base map
- image_size: the size of each frame [width, height]
- map_to_render: the base map(s) we want animations for. Always provided as a list. If more than one item is in the list, one animation per item will be rendered.
- render_single_borough: whether we want to focus on a single borough and render only the borough, or if we simply want to center and zoom on a borough but still render the rest of the map
- filter_query_on_borough: whether we want to execute the query filtering on a borough, or if we want the results for the whole city
- title: the title to display in the animation
- db: the name of the database to connect to
- data_table: the table in which to fetch the data (in our case, the table in which we have the data for 2018)
- lookup_table: the taxi zone lookup table, to match a zone id with the name of a borough
- aggregated_result: the type of result we want from the query, either avg or count (note that the query results will always be structured 'PULocationID', 'DOLocationID', aggregated_result).
- time_granularity: if we want to filter for specific weekdays or we want results for every day in the provided period
- period: the time interval to consider for the query. If we want for a single date, start and end date should be inputted the same.
- weekdays: the index of the weekday(s) we want data for (0 being Monday, 6 being Sunday). If we want to filter on one or more weekday, time_granularity should be set to 'on_specific_weekdays'. If we we do not want to filter on any weekday, time_granularity should be set to 'period' and the array of weekdays left empty [].


**To render heat maps:**

|heat_map_dict = {'shp_path':shp_path, 'image_size':(1920,1080),'db':'nyc_taxi_rides', 
|                 'data_table':'passenger_count_2018','lookup_table':'taxi_zone_lookup_table', 
|                 'aggregated_result':'count', 'weekdays_vs_weekends':True,
|                 'period':['2018-01-01','2018-01-07'], 'render_single_borough':False,
|                  'filter_query_on_borough':False,'title':'Title'} 


Arguments:

- shp_path: the path to the shapefile used to render the base map
- image_size: the size of each frame [width, height]
- db: the name of the database to connect to
- data_table: the table in which to fetch the data (in our case, the table in which we have the data for 2018)
- lookup_table: the taxi zone lookup table, to match a zone id with the name of a borough
- aggregated_result: the type of result we want from the query, either avg or count (note that the query results will always be structured 'PULocationID', 'DOLocationID', aggregated_result).
- weekdays_vs_weekends: flag to indicate whether we want to build the heat map looking at the difference of the flow between weekdays and weekends, or if we want the aggregated_result on the whole period.
- period: the time interval to consider for the query. If we want for a single date, start and end date should be inputted the same.
- render_single_borough: whether we want to focus on a single borough and render only the borough, or if we simply want to center and zoom on a borough but still render the rest of the map
filter_query_on_borough: whether we want to execute the query filtering on a borough, or if we want the results for the whole city
- title: the title to display on the heat map



Focus on some choices and decisions made
----------------------------------------

**Code structure choices**

Two comments here:

- I like when code is flexible, and I tend to want to pass as a parameter pretty much everything - so I used a lot of dictionaries as input objects for my functions
- I like when code is reusable - so I used a lot of functions

But although I tried my best to meet these two requisites, I also hard-coded some attributes in several functions, such as:

- the special dates calendar for 2018 (Christmas, National Day, hottest and coldest day, ....)
- the colours to render
- the positions of the text displayes (legend, titles, ...)
- the scaling of the points 
- the number of frames per second to render

Besides, as mentioned before we use the pick up date as a reference date to assign the flow of passenger to a travel date


**Rendering choices for the animation rendering**

Regarding the colour code used:
- I chose a black background to illuminate the map and allow contrast to be more visible
- I picked the viridis color palette. Although recommended for its smooth transitions that specifically applied to heat maps, I also used two colors to represent the dots in the animations.

Regarding the video parameters:
- I chose a rather high resolution (1920x1080) to allow the image to be of good quality (the more details the better without exageration)
- I chose to render 30 fps, to give time to see the animation at normal speed. But I could have gone for 60 to be able to record in slow motion using video editing afterwards

Regarding the plot itself:
- I chose to normalize the weight of the point based on the max number of passengers which means that from one day to another, although the biggest point will have the same size, it will not represent the same number of passengers (compromise to prevent having huge differences between the points, or squishing too much the scale by using a log.
- What is represented is actually the flow of people from one zone to another, extrapolated to make the point move between its origin and its destination. I.e not an itinerary, not a time related position of people. Just an animation of the flow of people between one origin and one destination, averaged or counted per day. 


**Rendering choices for the heat map rendering**

Regarding the colour code used:
- To be consistent with the animation choiced, I chose a black background to illuminate the map and allow contrast to be more visible
- However, I used another color palette, where darker (closer to the background color) means few people traveling and lighter means more people traveling. To plot the difference between weekdays and weekends, we use two different tones for positive and negative values, but the logic is the same.


Regarding the plot itself:
- There is no normalization of the weight, but a linear choice of color depending on the value. 
- One map is dedicated to one zone, highlighted with a thicker outline.


**Libraries choices**

The comments regarding the libraries are the same.

- I chose to use OpenCV as I was dealing with rendering images and videos. Although it makes it almost trivial to render an image and a video, there are two main limitations I didn't manage to come across:
- the size of the text can only be specified as an integer, as well as the diameter and center of a circle
- there is no relative positioning (we have to specify the position of one pixel used as a reference to draw the shape or the text).


Regarding the other libraries, they appeared as the most appropriate for the task to be performed, and I tried to limit them to the strict minimum.
Note that I used a library for the projection of the coordinates in the first approach, but I ended up writting my own projection function when working on the second approach. 



Documentation of the functions
------------------------------

Each function is documented below (purpose, input and output). Most functions are used for both the rendering of the heat map and the animation. See the code flow documentation (above) and graph for more details.

**build_query_dict(render_animation_dict)**

    This function builds the query dictionary that will be used to query the database.
    Provided several arguments regarding the type of query we want to make, it generates
    a new dictionary that can simply be injected as an argument to the prepare_sql_query
    function. 
    
    The input of this function could look like the example below
    
|    render_animation_dict = {'time_granularity':'period', 'period':['2018-01-01','2018-01-01'] ,  
|                 'weekdays':[0, 1, 2, 3, 4],'filter_query_on_borough':'Manhattan', 
|                 'base_map':test_map,'map_type':'Manhattan', 'image_size':[1920, 1080],
|                 'shape_dict':shape_boundaries, 'df_sf':df_sf, 
|                 'database':'nyc_taxi_rides', 'data_table':'taxi_rides_2018', 
|                 'lookup_table':'taxi_zone_lookup_table', 'aggregated_result':'avg'}
    
    Note that:

    - time_granularity can have three different values : 'period', 'specific_weekdays'.
    - if time_granularity is set to specific_weekdays, then 'weekdays' must have an array 
    with the indexes of the days to query (0 = Monday, 1= Tuesday, ...).
    - if time_granularity is set to period, then 'period' must have an array with start and
    end date. If only a single date is to be queried, the period type should be used, 
    inputting the same date as start date and end date (ex: ['2018-01-01','2018-01-01']).
    - the filter_query_on_borough argument is used to filter the query on a specific
    borough (independent from the map_type rendering constraint that will render only a 
    single borough). It can be provided as False (i.e we don't want to filter the query on
    a single borough), or with the name of the borough to filter the results on.
    
    Input: the dictionary providing all the details of the rendering we want to make,
    including what data we want (i.e arguments to pass in the database query) and the
    rendering specifications (unused in this function). 
    
    Output: the dictionary to pass as an argument to the function that generated the
    formatted query input.



**calculate_boundaries(points)**

    This function returns the coordinates of the max and min points of the boundaries
    of a shape. 
    It is used for a single shape (i.e. finding the extreme limits of a shape) as well
    as for the entire map. 

    Input: list of tuples of coordinates of a shape, or list of all the max and min
    sets of coordinates of all the shapes of the map. 
    
    Output: the coordinates of the most extreme points of the targeted area (shape or map)


**calculate_centroid(points)**

    Given a list of tuples of coordinates this function calculates the mean on each axis.
    This is used to obtain the center of a given shape, through the list of points of its
    boundaries.

    Input: list of tuples of coordinates of a shape
    
    Output: the center coordinates of the shape


 **compute_color(weight, min_passenger, max_passenger)**

    This function returns a BGR array associated with the color_index of a color palette.
    The color_index is calculated using the weight we want to represent on the heat map (the
    number of passengers between two zones, in a dynamic scale depending on the min and max
    number of passengers traveling to and from a given zone for which we draw the maps.

    Input: the weight value, the min and max values of passengers
    
    Output: a BGR color array


**compute_min_max_passengers(trips_list)**

    This function returns the min and max values of passengers associated to the traffic
    of a particular zone (incoming or outgoing flow of people). 

    Note that this function has been used only for the heat map rendering but could as well
    have been used for the animation rendering.

    Input: list of tuples, with for each tuple the id of the linked zone (i.e a zone people
    come from to go to the zone we are look at, or coming from) and the associated number
    of passengers.
    
    Output: the min and max number of passengers associated to a single zone.


**compute_weight(map_type, weight, max_passenger)**

    This function calculates the diameter of the point to render on the map based
    on the type of map rendered (zoom on a borough or not) and the value of the 
    aggregated_result of the query (count or avg of passengers on a given 
    itinerary. The calculation is actually a normalisation of the values of the
    aggregated_result.

    Input: the map_type (for the scaling), the weight for a single link and the
    max_number of passengers for the time interval observed. 
    
    Output: the value of the normalized weight to use to render a point.


**convert_id_shape(idx, inverse = False)**

    This function converts the id index either from the database query result to the 
    shape_dict index (inverse = False, we want to substract 1), or the inverse (inverse = True).
    This function is useful due to the fact that in the database we use the zone id (index
    from 1 to 263), and with the shape_dict (from the shapefile) we use the row indexes 
    (from 0 to 262).

    Input: the index and the direction of the conversion we want to perform
    
    Output: the index converted.


**convert_projection(x, y, projection, inverse=False)**

    This function converts coordinates from one projection system to another.
    As to simplify centering later on, we also translate the coordinates to the origin. In
    the case of an inversed projection, we move back the points to their initial absciss. 
    
    Input: x an y coordinates to convert, as well as the "direction" of 
    the projection (i.e whether we want to project from the original coordinate system
    to the image scale (inverse = False), or the inverse (inverse = True).
    
    Output: the x and y coordinates in the new coordinate system.


**convert_shape_boundaries(zone_shape_dict, projection)**

    This function edits the dictionary with the shape boundaries coordinates by converting
    them to the image scale 'coordinate' system.  

    Input: shape boundaries dictionary in the initial coordinate system
    
    Output: a dictionary with for each zone id the set of boundary coordinates 
    in the image scale, centered.


**define_projection(map_max_bound, map_min_bound, image_size)**

    This function compute the projection parameter using the coordinates of the max and
    min points of the area to draw (that we call the map).
    It returns the conversion factor value as well as the axis to use to center the area in 
    the image after the conversion.
    If with the conversion the y-axis is used to scale the image (i.e. the map 'fits' the
    image on the y_axis), we will have to center the map on the x-axis. 
    
    Note that the image size is hard-coded in this function (high resolution). 
    
    Input: max and min boundaries coordinates tuples of the map to draw
    
    Output: a dictionary with the parameters to perform the projection


**display_general_information_text(image, map_type, video_title)**

    This function writes text common to all frames, on the base map in particular.

    Input: the image of the base map to write on, the map_type to be able to append
    the name of a borough if necessary and the video title as provided by the user.
    
    Output: the base map including the legend and the title or the map. 


**display_scale_legend(map_image, font, min_pass, max_pass, colors)**:

    This function generates dynamically a color bar scale for a given map, 
    using the min and max values represented, and the compute_color function.

    Input: the map on which to draw the legend bad, the font to write the 
    associated text, the min and max values for the flow and all the colors 
    used on the map as an array.
    
    Output: a color bar plotted on the map for the legend

 
**display_specific_text(rendered_frame, date, map_type, min_pass, max_pass)**

    This function writes text on a given frame. the text we want to write is 
    the weekday, the date, and whether it is a special date or not.
    These specific dates are considered for 2018 only (hard-coded).

    Input: the frame to write on, the date (as this is what we want to write), as
    well as the value of the max number and min number of passengers that day to
    display the legend of the size of the circles.
    
    Output: the text is added to the frame.


**draw_base_map(draw_dict)**

    This function returns a base map image of the zone we want to render. It is provided
    a dictionary with the parameters of the rendering. Such dictionary should look like the
    example below.
|    draw_dict = {'image_size':[1920, 1080], 'map_type':'Manhattan', 
|             'title':'Passenger flow on Mondays of Jan 2018 in total', 
|             'shape_dict':shape_boundaries, 'df_sf':df_sf}
    
    Input: a dictionary with the attributes of the rendering, such as the image size, 
    the title, the targeted area to draw (total for the whole city, or a single borough
    provided with its name), the shape boundaries dictionary in the initial coordinate 
    system, and the dataframe obtained from the shapefile (to make the association of 
    zone id and borough name).
    
    Output: the image of the base map as well as the projection used to draw it.


**find_max_coords(shape_dict)**

    This function is used to obtain the set of max and min coordinates of an entire map.
    It uses another function to perform the comparison of the values of the
    coordinates (calculate_boundaries). 

    Input: the shape dictionary, in which for all shape there is the max and min tuples. 
    The function regroups all the max and min into a list to use the calculate_boundaries
    function.
    
    Output: the coordinates of the most extreme points of the map.


 **find_names(zone_id, df_sf)**

    This function simply returns the name of the zone associated to a zone_id as well
    as the name of the borough it belongs to.

    Input: zone_id, dataframe extracted from the shapefile to find the correspondance
    between an id and the names.
    
    Output: the zone name and its borough name.


**get_shape_set_to_draw(map_type, shape_dict, df_sf, image_size)**

    This function returns the dictionary of all shapes that will be drawn on the base
    map, depending on the choice of the user to draw either the whole city or just a borough.
    The dictionary is indexed per zone_id (0 to 262, so would need conversion to match the
    index scale of PULocationID and DOLocationID, 1 to 263), with for each zone a dictionary
    with all relevant *converted* coordinates (boundary points, center, max and min boundary
    points). 
    Note: we perform the conversion on the coordinates of the shapes we want to draw only. 
    This is why we first reduce the dictionary of shapes to draw to a borough if needed. 
    
    Input: the targeted base map type, the shape boundaries dictionary in the 
    initial coordinate system, the image_size (to calculate the projection parameters) and
    the dataframe obtained from the shapefile (to select only zones from a specific borough).
    
    Output: a dictionary for only the zones to draw with the boundary coordinates 
    in the image scale, and centered, as well as the projection used.


**interpolate_next_position(origin_coords, destination_coords, tot_frames, curr_frame)**

    This function calculates the position of a point to render on a map based on
    the distance to cross (between origin and destination), in the total number of frames
    we want (for example 60), and based on the current frame we are rendering.
    The idea is to go from origin to destination in tot_frames, moving a little bit
    between each frame. 

    Input: the coordinates of the origin and destination, to know the distance to cross,
    the total number of frames we have to cross this distance, and the current frame we
    render to know where the point should be. 
    
    Output: the coordinates of the point to render at the given frame. 


**make_flow_animation(animation_dict)**

	This is the main script to render animations. It accepts a dictionary as input (see
	above the details about the input), and returns the animations processed according
	to the parameters set by the user. 

	Input: rendering parameters dictionary

	Output: video(s) of the animations.


**make_video_animation(frames, image_size, map_type)**

    This function renders the animation using all the frames already rendered. 
    
    Input: all the frames to append to the video, the image size and the map_type used to 
    build the title of the video. 
    
    Output: the animation as a .avi file. 


**make_sql_query(query, database)** 

    This function connects to the database and execute the query. It returns the result
    as an array of tuples. 

    Input: the formatted query and the database to execute the query on.
    
    Output: the query results.


**prepare_heat_map_sql_query(query_dict)**

	This function is very similar to the prepare_sql_query used for the animation.
	It returns the query to execute on the database, which result will be used
	to be plotted on the base map as to build visualizations. 
	It is provided a dictionary with the parameters of the query. 
	Such dictionary should look like the example below.

|	query_dict = {'data_table':'taxi_rides_2018', 'lookup_table':'taxi_zone_lookup_table', 
|	              'aggregated_result':'avg', 'date':single_date, 
|	              'specific_weekdays':'weekdays_vs_weekends', 'filter_query_on_borough':'Manhattan'}

	Input: a dictionary with the attributes of the query, such as

	- the data table (year table) and the lookup table (that will match the zone id with 
	the borough name if we want to filter the query on a single borough)
	- the type of aggregated result we want (count or avg)
	- the time granularity: for a period and whether we want to compute the difference between
	weekdays traffic and weekends traffic
	- whether we want to filter the query on a single borough

	Note that:

	- the query results will always be structured 'PULocationID', 'DOLocationID', 
	aggregated_result on the passenger_count column. If we wanted to fetch other data (other
	columns, or the aggregated_result type on a another column), we would need to change the
	format of the query in this function (MySQL syntaxt).

	Output: the query to execute formatted.


**prepare_sql_query(query_dict)**

    This function returns the query to execute on the database, which result will be used
    to be plotted on the base map as to build visualizations. 
    It is provided a dictionary with the parameters of the query. 
    Such dictionary should look like the example below.
    
|    query_dict = {'data_table':'taxi_rides_2018', 'lookup_table':'taxi_zone_lookup_table', 
|                  'aggregated_result':'avg', 'date':single_date, 
|                  'specific_weekdays':'on_specific_weekdays', 'filter_query_on_borough':'Manhattan'}
    
    
    Input: a dictionary with the attributes of the query, such as

    - the data table (year table) and the lookup table (that will match the zone id with 
    the borough name if we want to filter the query on a single borough)
    - the type of aggregated result we want (count or avg)
    - the time granularity: for a single date (multiple queries should be made for each 
    date if the rendering is wanted for a time period)
    - whether we want to filter the query on a single borough
    
    Note that:

    - the specific_weekdays argument is used by another function to filter the 
    single_date to pass.
    - the query results will always be structured 'PULocationID', 'DOLocationID', 
    aggregated_result on the passenger_count column. If we wanted to fetch other data (other
    columns, or the aggregated_result type on a another column), we would need to change the
    format of the query in this function (MySQL syntaxt).
    
    Output: the query to execute formatted.  


 **process_heat_map_query_results(query_results)**

    This function transforms the results of the query (provided in the form of a list
    of tuples (origin_zone_id, destination_zone_id, number_passenger) into two dictionaries.
    These dictionaries are built using the zone_id as a key, and a list of tuples as a value. 
    The list of tuples contains the id of the zone 'linked' to the key zone id and the weight 
    (number of passengers) of that link. So basically, in the incoming dictionary we have as 
    a key the zone_idof the zones where people *go to*, and as a list the zone id of where 
    they come from and how many people went. 
    For example, for a given period, n passengers went to zone A coming from zone B, 
    m passengers coming from zone C. The dictionary will look like this:

| 	incoming_dict = {'A';[(B, n), (C,m)]}

	The logic is the same for the outgoing flow, except that the tuple now contains the 
	zone_id of the zones where people *go* while coming from the key zone. 


    Input: the query results
    
    Output: two dictionaries, incoming and outgoing flow


**process_shape_boundaries(df_sf, sf)**

    This function builds a dictionary with the shape boundaries coordinates before conversion,
    for each zone id available in the shape file. 

    Input: shapefile and dataframe converted from the shapefile (the dataframe is used only
    to get the zone_id number).
    
    Output: a dictionary with for each zone id the set of boundary coordinates the initial
    coordinate system.


**reduce_shape_dict_to_borough(shape_dict, df_sf, borough_name)**

    This function returns a reduced dictionary of shapes limited to the borough which name
    is provided as an argument. 
    The dictionary is indexed per zone_id (0 to 262, so would need conversion to match the
    index scale of PULocationID and DOLocationID, 1 to 263), with for each zone a dictionary
    with all relevant coordinates (boundary points, center, max and min boundary
    points) in the original coordinate system (since the dictionary provided as an input is
    not yet converted).
    
    Input: the shape boundaries dictionary in the initial coordinate system, the borough 
    name we want to select zones from and the dataframe obtained from the shapefile 
    (to make the association of zone id and borough name).
    
    Output: a dictionary for only the zones to draw with the of boundary coordinates 
    in the initial coordinate system.


**render_all_frames(render_frame_dict)**

    This function renders all the frames of a single date (60 frames per date), and returns
    the list of frames as a list, that is then used by another function to build the 
    video of the animation.
    
    The input dictionary can be as follows:
|    render_frame_dict = {'query_dict':query_dict, 'database':database,
|                        'base_map':base_map, 'converted_shape_dict': converted_shape_dict,
|                        'map_type':map_type, 'frames': frames,
|                        'video_title': title}
                        
    
    The arguments are:

    - query_dict: all the details needed to build the query prior to executing it
    - database: the database to connect to
    - base_map: the map to plot the points on
    - converted_shape_dict: the dictionary with the shapes converted to the coordinate
    system of the base map we use
    - map_type: whether we want to center on a single borough (and either plot it alone or
    with other boroughs around), or the entire city map
    - frames: the list of frames already rendered (we want to append all frames of the video)
    - video_title: the name to give to the 


    Input: a dictionary with the arguments provided by the user on what and how to render.
    
    Output: all the frames to build the animation on. 


**render_animation_query_output(render_animation_dict)**

    This function renders the animation using all the arguments provided by the user
    on how to render it (what to render, what query to make, ...).
    It relies on a lot of other functions, such as the function that builds the 
    animation, builds the query, executes the query,....
    
    The input dictionary can be as follows:
|    render_animation_dictrender_frame_dict = {'time_granularity':time_granularity, 'period':period,  
|         'weekdays':weekdays,'filter_query_on_borough':filter_query_on_borough, 
|         'base_map':base_map,'projection':projection, 'map_type':map_type,
|        'image_size':image_size,'shape_dict':shape_boundaries, 'df_sf':df_sf, 
|         'database':database, 'data_table':data_table, 
|         'lookup_table':lookup_table, 'aggregated_result':aggregated_result}
    
    The arguments are:

    - time_granularity: if we want to plot for a whole period or specific weekdays (see
    function build_query_dict for more details)
    - period: the start and end dates we want to plot for (see function build_query_dict
    for more details)
    - weekdays: the specific weekdays indexes we want to query (see function build_query_dict
    for more details)
    - filter_query_on_borough: if we want the query to return only rows for a single
    borough, as opposed to the whole city
    - base_map: the map to plot the points on
    - projection: the projection used to plot the base map, as to plot on the same scale
    the points to render on top of the base map
    - map_type: whether we want to center on a single borough (and either plot it alone or
    with other boroughs around), or the entire city map
    - image_size: the size of each frame in pixels
    - shape_dict: the boundaries dictionary (see function process_shape_boundaries for more
    details)
    - df_sf: the dataframes extracted from the shapefile, used solely to match a zone id to
    its borough, when limiting the rendering to a borough
    - database: the database to connect to
    - data_table: the table on which to run the queries
    - lookup_table: the table used to match the zone id with a borough, when limiting the
    results of a query to a borough
    - aggregated_results: either count or avg, the aggregation of the data we want on the
    number of passengers commuting.
    - render_single_borough: whether we have a single borough rendered or the whole map (that
    can be focused on a borough)

    Note that we have two arguments related to the borough:

    - map_type, to know what base map we want to draw (either full map or only a borough)
    - filter_query_on_borough, dedicated to the query (we may want to query for the whole city
    but plot only on a borough and see points cominng from or going outside the borough
    boundaries, or we may want to reduce our query results to the borough we are plotting)
    

    Input: a dictionary with the arguments provided by the user on what and how to render.
    
    Output: the animation as a .avi file. 


 **render_frame(frame, base_map, query_results, converted_shape_dict, map_type)**

    This function renders a single frame on a copy of the base map using the query results,
    the shape dictionary converted to the proper coordinate system and another function
    dedicated to rendering the point on the image. 

    Input: the base map to use as a reference, the query results, the shape coordinates
    dictionary to get the coordinates of the centers of the shape (to render the points),
    the current frame number being rendered as well as whether we render a single borough or
    not.
    This last argument is used to scale the size of the points (made smaller if the full
    map is rendered, and bigger otherwise). 
    
    Output: the image of the frame with the points rendered based on the query results.
  

**render_point_on_map(x_point, y_point, weight, base_map, colour)**

    This function simply renders a circle at the x and y coordinates provided, on the
    base map provided, and with a diameter matching the weight given. 
    The weight being for example the count of passengers that went from one zone to another.
    If the origin and the destination are the same, the point is rendered in a different
    color. 

    Input: the index and the direction of the conversion we want to perform
    
    Output: the index converted.


**shp_to_df(sf)**

    This function extracts a dataframe from a shapefile. The dataframe obtaines is used 
    to access more efficiently the list of indexes as well as doing the association
    between a zone id and its associated borough to be able to filter on a borough.

    Input: shapefile
    
    Output: associated dataframe of the input shapefile








**make_heat_map(heat_map_dict)**

    This function extracts a dataframe from a shapefile. The dataframe obtaines is used 
    to access more efficiently the list of indexes as well as doing the association
    between a zone id and its associated borough to be able to filter on a borough.

    Input: shapefile
    
    Output: associated dataframe of the input shapefile


**render_heat_map_query_output(render_heat_map_dict)**

    This function extracts a dataframe from a shapefile. The dataframe obtaines is used 
    to access more efficiently the list of indexes as well as doing the association
    between a zone id and its associated borough to be able to filter on a borough.

    Input: shapefile
    
    Output: associated dataframe of the input shapefile

**render_map(render_map_dict)**

    This function extracts a dataframe from a shapefile. The dataframe obtaines is used 
    to access more efficiently the list of indexes as well as doing the association
    between a zone id and its associated borough to be able to filter on a borough.

    Input: shapefile
    
    Output: associated dataframe of the input shapefile














 














-----------------------------
Further work and improvements
-----------------------------

Several paths could be followed to improve the code and the analysis, for example:
- refactoring the code to use classes (OOP)
- make the heat map function more flexible (choose which maps to render)
- represent the variation over time withing one day
- comparing the flow of passengers with the public transportation network, and try to find patterns
- conduct the analysis on a larger dataset, including previous years, or other taxi types (green taxis, FHV)
- observe other parameters than only the passenger count, for example the number of passenger per ride, the spread over time in a day,....


-----------------------------
Sources and acknowlegments
-----------------------------

First of all, this project wouldn't exist if the TLC did not publish this huge dataset. Having access to such amazing source of information is incredible, and I am grateful it was made possible!

Besides using extensively the documentation of the libraries used, I also looked for help on forums, blog posts, ... the following were particularly useful:
Stackoverflow for technical difficulties
https://towardsdatascience.com/basic-time-series-manipulation-with-pandas-4432afee64ea
https://towardsdatascience.com/mapping-geograph-data-in-python-610a963d2d7f
https://www.kennethmoreland.com/color-advice/
https://medium.com/@enriqueav/how-to-create-video-animations-using-python-and-opencv-881b18e41397


While looking at this famous data compilation, I came accross this content that is worth taking a look at!
https://toddwschneider.com/posts/analyzing-1-1-billion-nyc-taxi-and-uber-trips-with-a-vengeance/#taxi-weather
https://chih-ling-hsu.github.io/2018/05/14/NYC
https://www.kdnuggets.com/2017/02/data-science-nyc-taxi-trips.html
https://medium.com/@linniartan/nyc-taxi-data-analysis-part-1-clean-and-transform-data-in-bigquery-2cb1142c6b8b
https://colossus.mapd.com/dashboard/10

Finally, this was the first project I conducted on my own from beginning to end, and I am grateful for the all the support I had!


