import tensorflow as tf
from tensorflow.keras.applications import MobileNetV2
from tensorflow.keras.models import Model
from tensorflow.keras.layers import Dense, GlobalAveragePooling2D, Dropout
from tensorflow.keras.preprocessing.image import ImageDataGenerator
from tensorflow.keras.callbacks import EarlyStopping, ModelCheckpoint, CSVLogger, ReduceLROnPlateau
from tensorflow.keras.regularizers import l2
from sklearn.utils.class_weight import compute_class_weight
import numpy as np

# ================= DATA GENERATORS ==================

train_datagen = ImageDataGenerator(
    rescale=1./255,
    rotation_range=40,
    zoom_range=0.4,
    width_shift_range=0.2,
    height_shift_range=0.2,
    shear_range=0.2,
    horizontal_flip=True,
    fill_mode='nearest'
)

test_datagen = ImageDataGenerator(rescale=1./255)

train_generator = train_datagen.flow_from_directory(
    r"C:\Users\Bhumi Jain\OneDrive\Desktop\human_eye_disease_prediction_1\dataset\train",
    target_size=(224,224),
    batch_size=16,
    class_mode='categorical'
)

test_generator = test_datagen.flow_from_directory(
    r"C:\Users\Bhumi Jain\OneDrive\Desktop\human_eye_disease_prediction_1\dataset\test",
    target_size=(224,224),
    batch_size=16,
    class_mode='categorical'
)

# ================= CLASS WEIGHTS ==================

classes = train_generator.classes
class_weights = compute_class_weight('balanced', classes=np.unique(classes), y=classes)
class_weights = dict(enumerate(class_weights))

# ================= LOAD MOBILENET ==================

base_model = MobileNetV2(weights="imagenet", include_top=False, input_shape=(224,224,3))

# Fine-tune last 30 layers
for layer in base_model.layers[:-30]:
    layer.trainable = False
for layer in base_model.layers[-30:]:
    layer.trainable = True

# ================= CUSTOM CLASSIFIER ==================

x = base_model.output
x = GlobalAveragePooling2D()(x)
x = Dense(256, activation='relu', kernel_regularizer=l2(0.001))(x)
x = Dropout(0.4)(x)
x = Dense(128, activation='relu')(x)
x = Dropout(0.3)(x)
output = Dense(train_generator.num_classes, activation='softmax')(x)

model = Model(inputs=base_model.input, outputs=output)

# ================= COMPILE MODEL ==================

model.compile(
    optimizer=tf.keras.optimizers.Adam(learning_rate=0.00005),
    loss='categorical_crossentropy',
    metrics=['accuracy']
)

# ================= CALLBACKS ==================

early_stop = EarlyStopping(monitor='val_loss', patience=5, restore_best_weights=True)
checkpoint = ModelCheckpoint("eye_disease_best_model.h5", save_best_only=True)
csv_logger = CSVLogger("training_log.csv", append=False)
reduce_lr = ReduceLROnPlateau(monitor='val_loss', factor=0.3, patience=3)

# ================= TRAIN MODEL ==================

history = model.fit(
    train_generator,
    validation_data=test_generator,
    epochs=20,
    class_weight=class_weights,
    callbacks=[early_stop, checkpoint, csv_logger, reduce_lr]
)

# ================= SAVE MODEL ==================

model.save("eye_disease_final_model.keras")
print("✅ Training Completed & History Saved!")