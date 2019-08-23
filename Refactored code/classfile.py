
class SQLQuery:

	def __init__(self):


##To be refactored
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
        results.append(result)

    cursor.close()

    return results