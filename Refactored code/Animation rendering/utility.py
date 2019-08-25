

class Utils:

    @staticmethod
    def calculate_centroid(points):

        x_sum = 0
        y_sum = 0
        for coords in points:
            x_sum += coords[0]
            y_sum += coords[1]

        x_mean = x_sum/len(points)
        y_mean = y_sum/len(points)

        return x_mean, y_mean

    @staticmethod
    def calculate_boundaries(points):

        x_max = -99999999
        x_min = 99999999
        y_max = -99999999
        y_min = 99999999

        for coords in points:
            if coords[0] > x_max:
                x_max = coords[0]
            if coords[0] < x_min:
                x_min = coords[0]
            if coords[1] > y_max:
                y_max = coords[1]
            if coords[1] < y_min:
                y_min = coords[1]

        max_bound = (x_max, y_max)
        min_bound = (x_min, y_min)

        return max_bound, min_bound

    @staticmethod
    def convert_id(idx, inverse=False):

        if inverse is False:
            idx = idx - 1
        else:
            idx = idx + 1

        return idx
