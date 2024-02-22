import json
import tempfile
import os
from ads.model.generic_model import GenericModel
from ads.model.model_metadata import MetadataCustomCategory


class StudioModel:
    def get_predefined_metadata(self, model_path: str):
        with open(
            os.path.join(os.path.dirname(__file__), "artifacts", "metadata.json"),
            "r",
            encoding="utf-8"
        ) as f:
            metadata = json.load(f)
            for key in metadata.keys():
                if model_path.startswith(key):
                    return metadata[key]
        return {}

    def create(self, model_path, object_storage_path, conda_env, compartment_id, project_id, **kwargs):
        predefined = self.get_predefined_metadata(model_path)
        with tempfile.TemporaryDirectory() as artifact_dir:
            generic_model = GenericModel(artifact_dir=artifact_dir)
            generic_model.prepare(
                inference_conda_env=conda_env,
                inference_python_version="3.9",
                score_py_uri=os.path.join(os.path.dirname(__file__), "artifacts", "score_vllm.py"),
                force_overwrite=True,
            )

            generic_model.metadata_custom.add(
                key='model_path',
                value=os.path.join(object_storage_path, model_path),
                category=MetadataCustomCategory.OTHER,
                description='OCI object storage URI for the model files',
                replace=True
            )
            generic_model.metadata_custom.add(
                key='base_model',
                value=model_path,
                category=MetadataCustomCategory.OTHER,
                description='',
                replace=True
            )
            if "image" in predefined:
                generic_model.metadata_custom.add(
                    key='image',
                    value=predefined["image"],
                    category=MetadataCustomCategory.OTHER,
                    description='',
                    replace=True
                )
            generic_model.save(
                display_name=model_path,
                compartment_id=compartment_id,
                project_id=project_id,
                ignore_introspection=True,
                reload=False
            )
        return generic_model