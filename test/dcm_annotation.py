from pydicom.dataset import Dataset, FileDataset, DataElement
from pydicom.sequence import Sequence
from pydicom.tag import Tag
import pydicom.uid
import os
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from PIL import Image
'''
Pseudo-Color Softcopy Presentation State Information Object Definition (IOD) 
A test file. Create DICOM file to save annotations. 
http://dicom.nema.org/dicom/2013/output/chtml/part03/sect_A.33.html
'''


def create_file_meta():
    file_meta = Dataset()
    file_meta.MediaStorageSOPClassUID = '1.2.840.10008.5.1.4.1.1.11.3'  # PseudocolorSoftcopyPresentationStageStorage
    file_meta.MediaStorageSOPInstanceUID = "1.2.276.0.7230010.3.1.4.296485376.1.1484917438.721089"
    file_meta.ImplementationClassUID = "1.2.3.4"
    file_meta.FileMetaInformationVersion = b'\x00\x01'
    file_meta.TransferSyntaxUID = '1.2.840.10008.1.2'
    file_meta.FileMetaInformationGroupLength = len(file_meta)
    return file_meta


def create_default_tags(filename, IS_IMPLICIT_VR, IS_LITTLE_ENDIAN):
    ds = FileDataset(filename, {}, preamble=b"\0" * 128, is_implicit_VR=IS_IMPLICIT_VR,
                     is_little_endian=IS_LITTLE_ENDIAN)
    # -----------------------------
    # IE: Patient
    # -----------------------------
    ds.PatientName = 'APERIO^CMU-2^SVS'
    ds.PatientID = 'APERIO^CMU-2^SVS'
    ds.PatientBirthDate = '19700101'
    ds.PatientSex = 'M'

    # -----------------------------
    # IE: Study
    # -----------------------------
    ds.StudyInstanceUID = '1.2.276.0.7230010.3.1.2.296485376.1.1484917433.721084'
    ds.StudyID = 'Annotation'
    ds.StudyDate = '20190212'
    ds.StudyTime = '130353.000000'
    # -----------------------------
    # IE: Series
    # -----------------------------
    # ds.Modality = 'SM'  #
    ds.SeriesInstanceUID = '1.2.276.0.7230010.3.1.3.296485376.1.1484917433.721085'
    ds.SeriesNumber = 0  # maybe need to correlated to WSI levels
    # -----------------------------
    # IE: Equipment
    # -----------------------------
    ds.Manufacturer = 'JJ'
    # -----------------------------
    # IE: PresentationState
    # -----------------------------
    dsPresentationStateIdentification = Dataset()
    dsPresentationStateIdentification.PresentationCreationDate = '20190212'
    dsPresentationStateIdentification.PresentationCreationTime = '130353.000000'
    ds.PresentationStateIdentification = dsPresentationStateIdentification

    # PresentationStateRelationship
    dsSeriesInstanceUID = Dataset()
    dsSeriesInstanceUID.SeriesInstanceUID = ds.SeriesInstanceUID
    sqReferencedImageSequence = Dataset()
    sqReferencedImageSequence.StudyInstanceUID = ds.StudyInstanceUID
    ds.ReferencedSeriesSequence = Sequence([dsSeriesInstanceUID, sqReferencedImageSequence])


    # ds.PresentationStateShutter =
    # ds.PresentationStateMask =
    # ds.Mask
    # ds.DisplayShutter
    # ds.BitmapDisplayShutter
    # ds.OverlayPlane =
    # ds.OverlayActivation =

    # DisplayedArea #TODO: need validation
    dsDisplayedArea = Dataset()
    dsDisplayedArea.PresentationSizeMode = 'TRUE SIZE'
    ds.DisplayedAreaSelectionSequence = Sequence([dsDisplayedArea])

    '''
    CORE
    '''
    # GraphicAnnotation = 6 #TODO: costumize your annotation, need validation
    seq = ds.GraphicAnnotationSequence = [Dataset(), Dataset()]
    img_seq1 = seq[0].ReferencedImageSequence = [Dataset()]
    # Graphics on the first referenced image
    obj_seq1 = img_seq1[0].TextObjectSequence = [Dataset()]
    obj_seq1[0].BoundingBoxAnnotationUnits = 'PIXEL'
    obj_seq1[0].BoundingBoxTopLeftHandCorner = [50, 50]
    obj_seq1[0].BoundingBoxBottomRightHandCorner = [100, 100]
    obj_seq1[0].BoundingBoxHorizontalJustification = 'LEFT'
    obj_seq1[0].UnformattedTextValue = 'Tumor'
    obj_seq1[0].GraphicGroupID = 1  # Annotation Label ID: 1

    img_seq2 = seq[1].ReferencedImageSequence = [Dataset()]
    obj_seq2 = img_seq2[0].GraphicObjectSequence = [Dataset(), Dataset()]
    obj_seq2[0].NumberofGraphicPoints = 4
    obj_seq2[0].GraphicType = "POINT"  # POINT POLYLINE INTERPOLATED CIRCLE ELLIPSE
    obj_seq2[0].GraphicData = [120, 60, 135, 75, 80, 125, 89, 139]
    obj_seq2[0].GraphicAnnotationUnits = 'PIXEL'
    obj_seq2[0].GraphicGroupID = 2  # Annotation Label ID: 2

    obj_seq2[1].NumberofGraphicPoints = 4
    obj_seq2[1].GraphicType = "POLYLINE"  # POINT POLYLINE INTERPOLATED CIRCLE ELLIPSE
    obj_seq2[1].GraphicData = [150, 80, 160, 80, 180, 120, 130, 120]
    obj_seq2[1].GraphicAnnotationUnits = 'PIXEL'
    obj_seq2[1].GraphicGroupID = 3  # Annotation Label ID: 2


    # ds.SpatialTransformation = "C" # Not Mandatory.  TODO: need validation

    # ds.GraphicLayer = "C" # Not Mandatory. TODO: need validation

    # ds.GraphicGroup =
    # ds.ModalityLUT=
    # ds.SoftcopyVOILUT =

    # PaletteColorLUT #TODO: need validation
    ds.RedPaletteColorLookupTableDescriptor = 8
    ds.GreenPaletteColorLookupTableDescriptor = 8
    ds.BluePaletteColorLookupTableDescriptor = 8

    ds.ICCProfile = b"CIELab"
    ds.SOPClassUID = '1.2.840.10008.5.1.4.1.1.77.1.6'
    ds.SOPInstanceUID = '1.2.276.0.7230010.3.1.4.296485376.1.1484917438.721089'
    return ds


def split_x_y(points):
    x = []
    y = []
    for idx, a in enumerate(points):
        if idx % 2 == 0:
            x.append(a)
        else:
            y.append(a)
    return x, y


fig, ax = plt.subplots(1)
Img = Image.open('./img_patch.jpg', 'r')
ax.imshow(Img)


def draw_bounding_box(top_left, bottom_right, text, color, SHOW_TEXT):
    bottom = bottom_right[0]
    left = top_left[1]
    w = bottom_right[1] - top_left[1]
    h = bottom_right[0] - top_left[0]
    rect = patches.Rectangle((bottom, left), w, h, linewidth=1, edgecolor=color, facecolor='none')
    ax.add_patch(rect)
    if SHOW_TEXT:
        plt.text(top_left[0], top_left[1], text, color=color)


def draw_points(points, color):
    x, y = split_x_y(points)
    plt.scatter(x, y, s=20, marker='*', c=color)


def draw_polyline(points, color, CLOSE):
    x, y = split_x_y(points)
    if CLOSE:
        x.append(x[0])
        y.append(y[0])
    plt.plot(x, y, color=color, linestyle='-')


def validate(dcm, color_map):
    print(dcm)
    GAS = dcm.GraphicAnnotationSequence
    RIS = GAS[0].ReferencedImageSequence
    obj_seq = RIS[0].TextObjectSequence
    box_text = obj_seq[0].UnformattedTextValue
    box_top_left = obj_seq[0].BoundingBoxTopLeftHandCorner
    box_bottom_right = obj_seq[0].BoundingBoxBottomRightHandCorner
    box_ID = obj_seq[0].GraphicGroupID
    draw_bounding_box(box_top_left, box_bottom_right, box_text, color_map[box_ID], True)

    RIS = GAS[1].ReferencedImageSequence
    obj_seq = RIS[0].GraphicObjectSequence
    point_data = obj_seq[0].GraphicData
    point_type = obj_seq[0].GraphicType
    point_ID = obj_seq[0].GraphicGroupID
    draw_points(point_data, color_map[point_ID])

    polyline_data = obj_seq[1].GraphicData
    polyline_type = obj_seq[1].GraphicType
    polyline_ID = obj_seq[1].GraphicGroupID
    draw_polyline(polyline_data, color_map[polyline_ID], True)

    plt.show()
    print("Validate dcm")


if __name__ == "__main__":
    IS_IMPLICIT_VR = True
    IS_LITTLE_ENDIAN = True
    color_map = ['k', 'r', 'g', 'b']
    save_to_dir = "./"
    filename = os.path.join(save_to_dir, "annotation_test.dcm")

    if not os.path.exists(filename):
        dcm = create_default_tags(filename, IS_IMPLICIT_VR, IS_LITTLE_ENDIAN)
        file_meta = create_file_meta()
        dcm.file_meta = file_meta
        dcm.save_as(filename, write_like_original=False)

    dcm_rd = pydicom.dcmread(filename)

    validate(dcm_rd, color_map)

    print(dcm_rd)
