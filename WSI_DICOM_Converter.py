import openslide
import os
import logging
from io import BytesIO
from pydicom.dataset import Dataset, FileDataset, DataElement
from pydicom.sequence import Sequence
from pydicom.tag import Tag
import pydicom.uid
from pydicom.encaps import encapsulate
import matplotlib.pyplot as plt


def range_subset(range1, range2):
    """Whether range1 is a subset of range2."""
    if not range1:
        return True  # empty range is subset of anything
    if not range2:
        return False  # non-empty range can't be subset of empty range
    if len(range1) > 1 and range1.step % range2.step:
        return False  # must have a single value or integer multiple step
    return range1.start in range2 and range1[-1] in range2


class frame_info:
    def __init__(self, img_level, locations, DimensionIndexValues, patch_size):
        self.img_level = img_level   # designate a image level for patch extraction
        self.locations = locations   # [[x1, y1], [x2, y2]...]  patch locations on the designated image level
        self.DimensionIndexValues = DimensionIndexValues  # [[1,1], [1, 2], [1, 3] ...] patch indexing
        self.patch_size = patch_size  # [512, 512] patch size


class parameters:
    def __init__(self, max_frame=500, patch_size=(512, 512), image_levels=None, JPEG_COMPRESS=True, Quality=75):
        self.max_frame = max_frame   # maximum frame count in one .dcm file
        self.patch_size = patch_size  # patch size of each frame
        self.image_levels = image_levels  # image levels that would like to be saved into Dicom files, i.e, range(0, 3). if None, save all the image levels
        self.JPEG_COMPRESS = JPEG_COMPRESS
        if self.JPEG_COMPRESS:
            self.IS_LITTLE_ENDIAN = True
            self.IS_IMPLICIT_VR = False
            self.Quality = Quality   # image quality of JPEG compression [0-100]
        else:
            self.IS_LITTLE_ENDIAN = True
            self.IS_IMPLICIT_VR = True


class WSIDICOM_Converter:
    def __init__(self, wsi_fn, save_to_dir, parameters):
        '''
        init function of WSI-to-DICOM converter
        :param wsi_fn: file name of WSI
        :param save_to_dir: directory to save the output dicom files
        :param parameters: parameters for convention, see class parameters
        '''
        self.wsi_obj = openslide.open_slide(wsi_fn)
        self.save_to_dir = save_to_dir
        self.instance_cnt = 0
        self._wsi_fn_ = os.path.splitext(os.path.basename(wsi_fn))[0]  # extract file name as Patient ID
        # relevant parameters
        self.max_frame = parameters.max_frame
        self.patch_size = parameters.patch_size
        self.image_levels = parameters.image_levels
        self.JPEG_COMPRESS = parameters.JPEG_COMPRESS
        if self.JPEG_COMPRESS:
            self.IS_LITTLE_ENDIAN = True
            self.IS_IMPLICIT_VR = False
            self.Quality = parameters.Quality
        else:
            self.IS_LITTLE_ENDIAN = True
            self.IS_IMPLICIT_VR = True

        # add default tags into a Dicom instance
        self.dcm_instance = self.add_default_elements()
        # generate essential information for patch extraction, so the patches can be saved into Dicom instances
        self.frame_items_info_list = self.generate_instance_info_list()

    # add information to default tags. (currently hard coded, can be loaded from yaml file)
    def add_default_elements(self):
        filename = os.path.join(self.save_to_dir, "compressed_instance_" + str(self.instance_cnt) + ".dcm")
        ds = FileDataset(filename, {}, preamble=b"\0" * 128,
                         is_implicit_VR=self.IS_IMPLICIT_VR, is_little_endian=self.IS_LITTLE_ENDIAN)
        ds.SpecificCharacterSet = 'ISO_IR 100'
        # ds.ImageType = ['ORIGINAL', 'PRIMARY', 'VOLUME', 'NONE']
        ds.SOPClassUID = '1.2.840.10008.5.1.4.1.1.77.1.6'  # VL Whole Slide Microscopy Image Storage
        # ds.SOPInstanceUID = '1.2.276.0.7230010.3.1.4.296485376.1.1484917438.721089'
        ds.StudyDate = '20170120'
        ds.SeriesDate = '20170120'
        ds.ContentDate = '20170120'
        ds.AcquisitionDateTime = '20170120130353.000000'
        ds.StudyTime = '130353.000000'
        ds.SeriesTime = '130353.000000'
        ds.ContentTime = '130353.000000'
        ds.AccessionNumber = '123456789'
        ds.Modality = 'SM'
        ds.Manufacturer = 'MyManufacturer'
        ds.ReferringPhysicianName = 'SOME^PHYSICIAN'
        ds.ManufacturerModelName = 'MyModel'
        ds.VolumetricProperties = 'VOLUME'
        if self.JPEG_COMPRESS:
            ds.PatientName = 'compressed_' + self._wsi_fn_
            ds.PatientID = 'compressed_' + self._wsi_fn_
        else:
            ds.PatientName = 'uncompressed_' + self._wsi_fn_
            ds.PatientID = 'uncompressed_' + self._wsi_fn_
        ds.PatientBirthDate = '19700101'
        ds.PatientSex = 'M'
        ds.DeviceSerialNumber = 'MySerialNumber'
        ds.SoftwareVersions = 'MyVersion'
        ds.AcquisitionDuration = 100
        ds.StudyInstanceUID = '1.2.276.0.7230010.3.1.2.296485376.1.1484917433.721084'
        # ds.SeriesInstanceUID = '1.2.276.0.7230010.3.1.3.296485376.1.1484917433.721085'
        ds.StudyID = 'NONE'
        # ds.SeriesNumber = 1
        ds.PatientOrientation = ''
        ds.ImageComments = 'http://openslide.cs.cmu.edu/download/openslide-testdata/Aperio/'

        ds_DimensionOrganization = Dataset()
        ds_DimensionOrganization.DimensionOrganizationUID = '1.2.276.0.7230010.3.1.4.296485376.1.1484917433.721087'
        ds.DimensionOrganizationSequence = Sequence([ds_DimensionOrganization])

        ds_DimensionIndex0 = Dataset()
        ds_DimensionIndex0.DimensionOrganizationUID = '1.2.276.0.7230010.3.1.4.296485376.1.1484917433.721087'
        ds_DimensionIndex0.DimensionIndexPointer = Tag(0x0048021E)
        ds_DimensionIndex0.FunctionalGroupPointer = Tag(0x0048021A)
        ds_DimensionIndex1 = Dataset()
        ds_DimensionIndex1.DimensionOrganizationUID = '1.2.276.0.7230010.3.1.4.296485376.1.1484917433.721087'
        ds_DimensionIndex1.DimensionIndexPointer = Tag(0x0048021F)
        ds_DimensionIndex1.FunctionalGroupPointer = Tag(0x0048021A)
        ds.DimensionIndexSequence = Sequence([ds_DimensionIndex0, ds_DimensionIndex1])

        ds_WholeSlideMicroscopyImageFrameType = Dataset()
        ds_WholeSlideMicroscopyImageFrameType.FrameType = ['ORIGINAL', 'PRIMARY', 'VOLUME', 'NONE']
        ds.WholeSlideMicroscopyImageFrameTypeSequence = Sequence([ds_WholeSlideMicroscopyImageFrameType])

        ds.SamplesPerPixel = 3
        # ds.PhotometricInterpretation = 'RGB'
        ds.PhotometricInterpretation = 'MONOCHROME2'

        ds.PlanarConfiguration = 0
        ds.Rows = self.patch_size[1]
        ds.Columns = self.patch_size[0]
        ds.BitsAllocated = 8
        ds.BitsStored = 8
        ds.HighBit = 7
        ds.PixelRepresentation = 0
        ds.BurnedInAnnotation = 'NO'
        ds.LossyImageCompression = '01'
        ds.LossyImageCompressionRatio = 10
        ds.LossyImageCompressionMethod = 'ISO_10918_1'
        # ds.LossyImageCompressionMethod = 'ISO_14495_1'
        ds.ContainerIdentifier = 'CI_12345'
        ds.IssuerOfTheContainerIdentifierSequence = []
        ds.ContainerTypeCodeSequence = []
        ds.AcquisitionContextSequence = []
        ds.ColorSpace = 'sRGB'

        ds_SpecimenDescription = Dataset()
        ds_SpecimenDescription.SpecimenIdentifier = 'Specimen^Identifier'
        ds_SpecimenDescription.SpecimenUID = '1.2.276.0.7230010.3.1.4.3252829876.4112.1426166133.871'
        ds_SpecimenDescription.IssuerOfTheSpecimenIdentifierSequence = []
        ds_SpecimenDescription.SpecimenPreparationSequence = []
        ds.SpecimenDescriptionSequence = Sequence([ds_SpecimenDescription])

        ds.ImagedVolumeWidth = 15
        ds.ImagedVolumeHeight = 15
        ds.ImagedVolumeDepth = 1

        ds_TotalPixelMatrixOrigin = Dataset()
        ds_TotalPixelMatrixOrigin.XOffsetInSlideCoordinateSystem = 20
        ds_TotalPixelMatrixOrigin.YOffsetInSlideCoordinateSystem = 40
        ds.TotalPixelMatrixOriginSequence = Sequence([ds_TotalPixelMatrixOrigin])

        ds.SpecimenLabelInImage = 'NO'
        ds.FocusMethod = 'AUTO'
        ds.ExtendedDepthOfField = 'NO'
        ds.ImageOrientationSlide = ['0', '-1', '0', '-1', '0', '0']

        ds_OpticalPath = Dataset()
        ds_IlluminationTypeCode = Dataset()
        ds_IlluminationTypeCode.CodeValue = '111744'
        ds_IlluminationTypeCode.CodingSchemeDesignator = 'DCM'
        ds_IlluminationTypeCode.CodeMeaning = 'Brightfield illumination'
        ds_OpticalPath.IlluminationTypeCodeSequence = Sequence([ds_IlluminationTypeCode])
        ds_OpticalPath.ICCProfile = b'RGB'
        ds_OpticalPath.OpticalPathIdentifier = '1'
        ds_OpticalPath.OpticalPathDescription = 'Brightfield'
        ds_IlluminationColorCode = Dataset()
        ds_IlluminationColorCode.CodeValue = 'R-102C0'
        ds_IlluminationColorCode.CodingSchemeDesignator = 'SRT'
        ds_IlluminationColorCode.CodeMeaning = 'Full Spectrum'
        ds_OpticalPath.IlluminationColorCodeSequence = Sequence([ds_IlluminationColorCode])
        ds.OpticalPathSequence = Sequence([ds_OpticalPath])

        ds_PixelMeasures = Dataset()
        ds_PixelMeasures.SliceThickness = 1
        ds_PixelMeasures.PixelSpacing = ['0.00025', '0.00025']
        PixelMeasuresSequence = Sequence([ds_PixelMeasures])
        ds_OpticalPathIdentification = Dataset()
        ds_OpticalPathIdentification.OpticalPathIdentifier = '1'
        OpticalPathIdentificationSequence = Sequence([ds_OpticalPathIdentification])

        SharedFunctionalGroupsSequence = Dataset()
        SharedFunctionalGroupsSequence.OpticalPathIdentificationSequence = OpticalPathIdentificationSequence
        SharedFunctionalGroupsSequence.PixelMeasuresSequence = PixelMeasuresSequence
        ds.SharedFunctionalGroupsSequence = Sequence([SharedFunctionalGroupsSequence])
        return ds

    # Generate patch extraction information for Dicom instance saving
    def generate_instance_info_list(self):
        frame_items_info_list = []
        org_w, org_h = self.wsi_obj.dimensions
        down_rate = self.wsi_obj.level_downsamples
        image_level_list = self.image_levels
        if image_level_list is None:
            image_level_list = range(self.wsi_obj.level_count)
        else:
            if not range_subset(image_level_list, range(self.wsi_obj.level_count)):
                raise Exception("Designated image levels exceed the range of original WSI image levels")
        for img_lv in image_level_list:
            fi_temp = frame_info(img_lv, [], [], self.patch_size)
            w_idx = 0
            for w in range(0, org_w, int(self.patch_size[0] * down_rate[img_lv])):
                w_idx += 1
                h_idx = 0
                for h in range(0, org_h, int(self.patch_size[1] * down_rate[img_lv])):
                    h_idx += 1
                    logging.debug("DimensionIndexValues: %d, %d" % (w_idx, h_idx))
                    if len(fi_temp.locations) < self.max_frame:
                        fi_temp.DimensionIndexValues.append([w_idx, h_idx])
                        fi_temp.locations.append([w, h])
                    else:
                        frame_items_info_list.append(fi_temp)
                        fi_temp = frame_info(img_lv, [], [], self.patch_size)
            if len(fi_temp.locations) > 0:
                frame_items_info_list.append(fi_temp)
        return frame_items_info_list

    # add frame sequence information into Dicom instance
    def add_Frame_Sequence_data(self, frame_items_info):
        self.dcm_instance.PerFrameFunctionalGroupsSequence = Sequence()
        for idx, dim_idx in enumerate(frame_items_info.DimensionIndexValues):
            ds_FrameContent = Dataset()
            ds_FrameContent.DimensionIndexValues = dim_idx
            FrameContentSequence = Sequence([ds_FrameContent])
            ds_PlanePositionSlide = Dataset()
            ds_PlanePositionSlide.XOffsetInSlideCoordinateSystem = 20 + (frame_items_info.locations[idx][0]) * 0.00025  # TODO: pixel size
            ds_PlanePositionSlide.YOffsetInSlideCoordinateSystem = 40 + (frame_items_info.locations[idx][1]) * 0.00025  # TODO
            ds_PlanePositionSlide.ZOffsetInSlideCoordinateSystem = 0
            ds_PlanePositionSlide.ColumnPositionInTotalImagePixelMatrix = int(frame_items_info.locations[idx][0] / self.wsi_obj.level_downsamples[frame_items_info.img_level]) + 1  # TODO
            ds_PlanePositionSlide.RowPositionInTotalImagePixelMatrix = int(frame_items_info.locations[idx][1] / self.wsi_obj.level_downsamples[frame_items_info.img_level]) + 1  # TODO
            PlanePositionSlideSequence = Sequence([ds_PlanePositionSlide])
            PerFrameFunctionalGroupsSequence = Dataset()
            PerFrameFunctionalGroupsSequence.PlanePositionSlideSequence = PlanePositionSlideSequence
            PerFrameFunctionalGroupsSequence.FrameContentSequence = FrameContentSequence
            self.dcm_instance.PerFrameFunctionalGroupsSequence.append(PerFrameFunctionalGroupsSequence)

    # create pixel data for Dicom instance
    def add_PixelData(self, frame_items_info):
        if self.JPEG_COMPRESS:
            encoded_framed_items = []
            for idx, f_loc in enumerate(frame_items_info.locations):
                img = self.wsi_obj.read_region(f_loc, frame_items_info.img_level, frame_items_info.patch_size).convert("RGB")
                instance_byte_str_buffer = BytesIO()
                img.save(instance_byte_str_buffer, "JPEG", quality=self.Quality, icc_profile=img.info.get('icc_profile'), progressive=False)
                t = instance_byte_str_buffer.getvalue()
                encoded_framed_items.append(t)
            return encoded_framed_items
        else:
            instance_byte_str = b''
            for idx, f_loc in enumerate(frame_items_info.locations):
                img = self.wsi_obj.read_region(f_loc, frame_items_info.img_level, frame_items_info.patch_size).convert("RGB")
                instance_byte_str += img.tobytes()
            return instance_byte_str

    # write data to Dicom files.
    def convert(self):
        # create file meta information
        file_meta = Dataset()
        file_meta.MediaStorageSOPClassUID = '1.2.840.10008.5.1.4.1.1.77.1.2'  # VL Microscopic Image Storage
        file_meta.MediaStorageSOPInstanceUID = "1.2.276.0.7230010.3.1.4.296485376.1.1484917438.721089"
        file_meta.ImplementationClassUID = "1.2.3.4"
        file_meta.FileMetaInformationVersion = b'\x00\x01'
        file_meta.FileMetaInformationGroupLength = len(file_meta)
        if self.JPEG_COMPRESS:
            # file_meta.TransferSyntaxUID = '1.2.840.10008.1.2.4.80'  # JPEG 2k
            # file_meta.TransferSyntaxUID = '1.2.840.10008.1.2.4.70'  # JPEG
            file_meta.TransferSyntaxUID = '1.2.840.10008.1.2.4.50'    # JPEG baseline
        else:
            file_meta.TransferSyntaxUID = '1.2.840.10008.1.2'  # default uncompressed

        # write data into Dicom instances
        self.instance_cnt = 0
        for frame_items_info in self.frame_items_info_list:
            print("Saving to instance %d/%d" % (self.instance_cnt, len(self.frame_items_info_list)))
            # update relevant tags
            self.dcm_instance.InstanceNumber = self.instance_cnt
            self.dcm_instance.SeriesInstanceUID = '1.2.276.0.7230010.3.1.3.296485376.1.1484917433.721085.'+str(frame_items_info.img_level)
            self.dcm_instance.SeriesNumber = frame_items_info.img_level
            print(frame_items_info.img_level)
            # self.dcm_instance.SOPInstanceUID = self.dcm_instance.SOPInstanceUID + str(self.instance_cnt)
            self.dcm_instance.SOPInstanceUID = '1.2.276.0.7230010.3.1.4.296485376.1.1484917438.721089.' + str(self.instance_cnt)
            self.dcm_instance.NumberOfFrames = len(frame_items_info.locations)
            self.dcm_instance.TotalPixelMatrixColumns, self.dcm_instance.TotalPixelMatrixRows = self.wsi_obj.level_dimensions[frame_items_info.img_level]
            self.add_Frame_Sequence_data(frame_items_info)
            # create encoded pixel data
            PixelData_encoded = self.add_PixelData(frame_items_info)
            if self.JPEG_COMPRESS:
                filename = os.path.join(self.save_to_dir, "compressed_instance_" + str(self.instance_cnt) + ".dcm")
                data_elem_tag = pydicom.tag.TupleTag((0x7FE0, 0x0010))
                enc_frames = encapsulate(PixelData_encoded, has_bot=True)
                pd_ele = DataElement(data_elem_tag, 'OB', enc_frames, is_undefined_length=True)
                self.dcm_instance.add(pd_ele)
            else:
                filename = os.path.join(self.save_to_dir, "instance_" + str(self.instance_cnt) + ".dcm")
                self.dcm_instance.PixelData = PixelData_encoded

            self.dcm_instance.file_meta = file_meta
            self.dcm_instance.save_as(filename, write_like_original=False)
            self.instance_cnt += 1


if __name__ == "__main__":
    wsi_fn = '/data/CMU-1-JP2K-33005.svs'
    wsi_dicom_dir = "/data/Dicom/temp"

    # p = parameters(JPEG_COMPRESS=False, image_levels=range(0, 3))
    # wsi_c = WSIDICOM_Converter(wsi_fn, wsi_dicom_dir, p)
    # wsi_c.convert()

    p = parameters(JPEG_COMPRESS=True)
    wsi_c = WSIDICOM_Converter(wsi_fn, wsi_dicom_dir, p)
    wsi_c.convert()

    # validate saved dicom
    fn = os.path.join(wsi_dicom_dir, 'instance_0.dcm')
    dcm = pydicom.dcmread(fn)
    img = dcm.pixel_array[0, :, :, :]
    plt.imshow(img)
    plt.title("uncompressed")
    plt.savefig("uncompressed_frame_10.jpg")
    plt.show()

    fn = os.path.join(wsi_dicom_dir, 'compressed_instance_0.dcm')
    compressed_dcm = pydicom.dcmread(fn)
    cmp_img = compressed_dcm.pixel_array[0, :, :, :]
    plt.imshow(cmp_img)
    plt.title("compressed")
    plt.savefig("compressed_frame_10.jpg")
    plt.show()

