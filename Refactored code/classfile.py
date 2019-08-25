import cv2
import numpy as np
import pandas as pd
import shapefile as shp

from utility import Utils


class ContextualText:

    def __init__(self, content, position, color):
        self.text_content = content
        self.font = cv2.FONT_HERSHEY_SIMPLEX
        self.font_style = cv2.LINE_AA
        self.position = position
        self.color = color
        self.text_size = 1
        self.thickness = 1

    def display_text(self, map_to_edit):
        text = self.text_content
        pos = self.position
        col = self.color
        font = self.font
        size = self.text_size
        thick = self.thickness
        style = self.font_style

        cv2.putText(map_to_edit, text, pos, font, size, col, thick, style)


class Map:

    def __init__(self, shapefile, image_size, background_color=[0, 0, 0]):
        self.shapefile = shapefile
        self.shape_dict = shapefile.shape_dict
        self.image_size = image_size
        self.max_bound = self.find_max_coords()[0]
        self.min_bound = self.find_max_coords()[1]
        self.projection = {}
        self.map_file = None
        self.background_color = background_color  # Default black background

    def find_max_coords(self):

        all_max_bound = []
        all_min_bound = []
        shape_dict = self.shape_dict

        for zone_id in shape_dict:
            zone_shape = shape_dict[zone_id]
            max_bound_zone = zone_shape.max_bound
            min_bound_zone = zone_shape.min_bound
            all_max_bound.append(max_bound_zone)
            all_min_bound.append(min_bound_zone)

        map_max_bound, unused_max = Utils.calculate_boundaries(all_max_bound)
        unused_min, map_min_bound = Utils.calculate_boundaries(all_min_bound)

        return (map_max_bound, map_min_bound)

    def render_map(self):

        # first we create a blank image, on which we will draw the base map
        width = self.image_size[0]
        height = self.image_size[1]
        # ex: size of the image 1080 height, 1920 width, 3 channels of colour
        base_map = np.zeros((height, width, 3), np.uint8)
        base_map[:, :] = self.background_color

        # we draw each shape of the dictionary on the blank image
        for shape_id in self.shape_dict:
            shape = self.shape_dict[shape_id]
            points = shape.points
            pts = np.array(points, np.int32)
            cv2.polylines(base_map, [pts], True, shape.color_line,
                          shape.line_thick, cv2.LINE_AA)

        self.map_file = base_map


class PointOnMap:

    def __init__(self, coordinates, weight, color):
        self.x_coord_or = coordinates[0]
        self.y_coord_or = coordinates[1]
        self.x_coord_curr = coordinates[0]
        self.y_coord_curr = coordinates[1]
        self.weight = weight
        self.color = color

    def render_point_on_map(self, base_map):
        x = int(self.x_coord_curr)
        y = int(self.y_coord_curr)
        cv2.circle(base_map, (x, y), self.weight, self.color, -1)

    def interpolate_next_position(self, target_coords, tot_frames, curr_frame):
        # as to perform the arithmetic operations, we convert everything to
        # float for more precision
        x_origin = float(self.x_coord_or)
        y_origin = float(self.y_coord_or)
        x_destination = float(target_coords[0])
        y_destination = float(target_coords[1])
        tot_frames = float(tot_frames - 1)
        curr_frame = float(curr_frame)

        delta_x = (x_destination - x_origin)/tot_frames
        delta_y = (y_destination - y_origin)/tot_frames

        # the rendering with OpenCV demands integers values for the positioning
        # so we convert x and y to int
        self.x_coord_curr = int(x_origin+delta_x*curr_frame)
        self.y_coord_curr = int(y_origin+delta_y*curr_frame)


class Projection:

    def __init__(self, map_to_scale, margin=[0, 0, 0, 0]):
        self.image_size = map_to_scale.image_size
        self.map_max_bound = map_to_scale.max_bound
        self.map_min_bound = map_to_scale.min_bound
        self.margin = margin  # (top, right, bottom, left) in pixels
        self.conversion = self.define_projection()[0]
        self.axis_to_center = self.define_projection()[1]

    def define_projection(self):

        # We get the max 'coordinates' for both the target image and
        # the shape we want to draw
        image_x_max = self.image_size[0] - self.margin[1]
        image_y_max = self.image_size[1] - self.margin[2]
        image_x_min = 0 + self.margin[3]
        image_y_min = 0 + self.margin[0]
        map_x_max = self.map_max_bound[0]
        map_y_max = self.map_max_bound[1]
        map_x_min = self.map_min_bound[0]
        map_y_min = self.map_min_bound[1]

        # we check which size is bigger to know based on which axis we want
        # to scale our shape to
        # we do the comparison using the aspect ratio expectations (dividing
        # each axis by the size of the target axis in the new scale)
        ratio_x = (map_x_max - map_x_min)/(image_x_max - image_x_min)
        ratio_y = (map_y_max - map_y_min)/(image_y_max - image_y_min)
        if ratio_x > ratio_y:
            conversion = 1 / ratio_x
            axis_to_center = 'y'  # we store the axis we will want to center on
            # based on which axis we perform the scaling from
        else:
            conversion = 1 / ratio_y
            axis_to_center = 'x'

        return conversion, axis_to_center

    def apply_projection(self, coords, inverse=False):

        x = coords[0]
        y = coords[1]
        x_min = self.map_min_bound[0]
        y_min = self.map_min_bound[1]

        if inverse is False:
            # to be able to center the image, we first translate the
            # coordinates to the origin
            x = (x - x_min) * self.conversion
            y = (y - y_min) * self.conversion
        else:
            x = (x + x_min) / self.conversion
            y = (y + y_min) / self.conversion

        coords = [x, y]
        return coords

    def apply_translation(self, coords):

        axis_to_center = self.axis_to_center
        image_x_max = self.image_size[0] - self.margin[1]
        image_y_max = self.image_size[1] - self.margin[2]
        image_x_min = 0 + self.margin[3]
        image_y_min = 0 + self.margin[0]
        map_x_max = self.map_max_bound[0]
        map_y_max = self.map_max_bound[1]
        map_max_converted = self.apply_projection((map_x_max, map_y_max))
        map_x_min = self.map_min_bound[0]
        map_y_min = self.map_min_bound[1]
        map_min_converted = self.apply_projection((map_x_min, map_y_min))

        if axis_to_center == 'x':
            map_x_max_conv = map_max_converted[0]
            map_x_min_conv = map_min_converted[0]
            center_translation = ((image_x_max - image_x_min)
                                  - (map_x_max_conv - map_x_min_conv))/2
        else:
            map_y_max_conv = map_max_converted[1]
            map_y_min_conv = map_min_converted[1]
            center_translation = ((image_y_max - image_y_min)
                                  - (map_y_max_conv - map_y_min_conv))/2

        # we center the map on the axis that was not used to scale the image
        if axis_to_center == 'x':
            coords[0] = coords[0] + center_translation
        else:
            coords[1] = coords[1] + center_translation

        # we mirror the image to match the axis alignment
        coords[1] = image_y_max - coords[1]

        return coords


class ShapeFile:

    def __init__(self, file_path):
        self.path = file_path
        self.shapefile = self.sf_reader(self.path)
        self.df_sf = self.shp_to_df()
        self.shape_dict = self.build_shape_dict(self.df_sf)

    def sf_reader(self, path):
        shapefile = shp.Reader(self.path)
        return shapefile

    def shp_to_df(self):
        sf = self.shapefile
        fields = [x[0] for x in sf.fields][1:]
        records = sf.records()
        shps = [s.points for s in sf.shapes()]
        df = pd.DataFrame(columns=fields, data=records)
        df = df.assign(coords=shps)
        return df

    def filter_shape_to_render(self, cond_stat, attr):
        # cond_stat in the form of a string or an array
        # attr in the form of a str, a column name of df
        try:
            if type(cond_stat) == str:
                filtered_df = self.df_sf[self.df_sf[attr] == cond_stat]
            elif type(cond_stat) == list:
                filtered_df = self.df_sf[self.df_sf[attr].isin(cond_stat)]

            return filtered_df
        except:
            print("Error parsing condition statement or attribute")
            print("Condition statement must be str or arr of values in the shapefile_dataframe")
            print("Attribute must be a column name of the shapefile_dataframe")
            print("See ShapeFile().df_sf for more details")

    def build_shape_dict(self, ref_df):
        index_list = ref_df.index.tolist()
        self.shape_dict = {}
        for shape_id in index_list:
            shape = ShapeOnMap(self.shapefile, shape_id)
            self.shape_dict[shape_id] = shape


class ShapeOnMap:

    def __init__(self, shapefile, shape_id):
        self.shapefile = shapefile
        self.shape_id = shape_id
        self.points = self.get_shape_coords()[0]
        self.center = self.get_shape_coords()[1]
        self.max_bound = self.get_shape_coords()[2]
        self.min_bound = self.get_shape_coords()[3]
        self.color_line = (255, 255, 255)  # Default white line
        self.line_thick = 1
        self.color_fill = (0, 0, 0)  # Default black fill

    def get_shape_coords(self):

        shape_zone = self.shapefile.shape(self.shape_id)
        points = [(i[0], i[1]) for i in shape_zone.points]
        x_center, y_center = Utils.calculate_centroid(points)
        center = (x_center, y_center)
        max_bound, min_bound = Utils.calculate_boundaries(points)

        return (points, center, max_bound, min_bound)

    def project_shape_coords(self, projection):

        shape_zone = self.shapefile.shape(self.shape_id)
        points = [projection.apply_projection([i[0], i[1]]) for i in shape_zone.points]
        points = [projection.apply_translation([i[0], i[1]]) for i in points]
        self.points = points

        x_center, y_center = Utils.calculate_centroid(points)
        self.center = (x_center, y_center)

        max_bound, min_bound = Utils.calculate_boundaries(points)
        self.max_bound = max_bound
        self.min_bound = min_bound

    def fill_in_shape(self, map_to_render):
        pts = np.array(self.points, np.int32)
        cv2.fillPoly(map_to_render, [pts], self.color_fill)
