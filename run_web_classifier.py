import multiprocessing
from functools import partial
import argparse
import logging

from transformers.hierarchy_processor import HierarchyProcessor
from classification_server.server import create_app
from classification_server.saved_model_classifier import (
    SavedModelClassifier,
    PredictionResult,
)

logger = logging.getLogger(__name__)


def model_worker(
    saved_model_dir: str,
    labels_path,
    hierarchy_file_path,
    to_model_queue: multiprocessing.Queue,
    from_model_queue: multiprocessing.Queue,
):
    model = SavedModelClassifier(saved_model_dir)
    processor = HierarchyProcessor(labels_path, hierarchy_file_path)

    while True:
        image_bytes, priors, index = to_model_queue.get()
        logger.info("GOTTEN!!!")
        result = model.predict(image_bytes)

        hierarchy_output = processor.compute(result.probabilities, priors)

        from_model_queue.put((result, hierarchy_output, index))


# TODO Capture signal to terminate


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--saved_model_dir", required=True)
    parser.add_argument("--labels_path", required=True)
    parser.add_argument("--hierarchy_file_path", required=True)

    args = parser.parse_args()

    to_classifier_queue: multiprocessing.Queue = PortableQueue()
    from_classifier_queue: multiprocessing.Queue = PortableQueue()

    worker_process = multiprocessing.Process(
        target=partial(
            model_worker,
            args.saved_model_dir,
            args.labels_path,
            args.hierarchy_file_path,
            to_classifier_queue,
            from_classifier_queue,
        )
    )
    worker_process.start()

    flask_app = create_app(to_classifier_queue, from_classifier_queue)
    flask_app.run("0.0.0.0", 8000)
