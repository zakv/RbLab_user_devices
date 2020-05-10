import ast

import numpy as np

from labscript_devices.IMAQdxCamera.blacs_tabs import IMAQdxCameraTab


class PCOCameraTab(IMAQdxCameraTab):

    # Override worker class.
    worker_class = 'userlib.user_devices.RbLab.PCOCamera.blacs_workers.PCOCameraWorker'

    def get_save_data(self):
        save_data = super().get_save_data()

        # Save info about plot settings if an image is plotted.
        image = self.image.image
        if image is not None:
            # Save the shape and dtype of the image.
            save_data['image_shape'] = repr(image.shape)
            save_data['image_dtype'] = str(image.dtype)

            # Get the view_box to access its settings.
            view_box = self.image.getImageItem().getViewBox()

            # Save x and y ranges.
            targetRange_x, targetRange_y = view_box.targetRange()
            save_data['targetRange_x'] = targetRange_x
            save_data['targetRange_y'] = targetRange_y

            # Save whether the x and y ranges are automatically adjusted.
            autoRange_x, autoRange_y = view_box.autoRangeEnabled()
            save_data['autoRange_x'] = autoRange_x
            save_data['autoRange_y'] = autoRange_y

            # Save color scale limits.
            color_scale_min, color_scale_max = self.image.getLevels()
            save_data['color_scale_min'] = color_scale_min
            save_data['color_scale_max'] = color_scale_max

        return save_data

    def restore_save_data(self, save_data):
        super().restore_save_data(save_data)

        # Restore plot settings if they were saved.
        if 'image_shape' in save_data and 'image_dtype' in save_data:
            # We have to display some image, otherwise the plot settings will be
            # overwritten once the first image is displayed. Restore a mostly
            # blank image of the saved size.
            image_shape = ast.literal_eval(save_data['image_shape'])
            image_dtype = np.dtype(save_data['image_dtype'])
            dummy_image = np.zeros(image_shape, dtype=image_dtype)
            # Make one pixel nonzero so histogram binning doesn't error.
            dummy_image[0, 0] = 1
            self.image.setImage(dummy_image)

            # Restore x and y ranges.
            try:
                view_box = self.image.getImageItem().getViewBox()
                view_box.setRange(
                    xRange=save_data['targetRange_x'],
                    yRange=save_data['targetRange_y'],
                )
            except KeyError:
                pass

            # Restore whether the x and y ranges are automatically adjusted.
            try:
                view_box.enableAutoRange(
                    x=save_data['autoRange_x'],
                    y=save_data['autoRange_y'],
                )
            except KeyError:
                pass

            # Restore color scale range.
            try:
                self.image.setLevels(
                    save_data['color_scale_min'],
                    save_data['color_scale_max'],
                )
            except KeyError:
                pass
