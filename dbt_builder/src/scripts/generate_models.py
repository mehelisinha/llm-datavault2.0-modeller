from __future__ import annotations

from pathlib import Path

from poc.metadata.reader import MetadataReader
from shared.src.logger.default_logger import default_logger
from dbt_builder.src.dv_components.manager.dv_component_manager import DVComponentManager

# ---------------------------------------------------------------------------
# Metadata model generator (OOP version)
# ---------------------------------------------------------------------------


class MetadataModelGenerator:
    def __init__(
        self,
        config_path: Path,
        output_path: Path,
        dry_run: bool = False,
        overwrite: bool = True,
    ):
        self.config_path = Path(config_path)
        self.output_path = Path(output_path)
        self.dry_run = dry_run
        self.overwrite = overwrite

    def run(self) -> None:
        default_logger.info(f"Loading metadata from: {self.config_path}")

        reader = MetadataReader(str(self.config_path))

        system = reader.system
        default_logger.info(f"System: {system['system_name']} ({system['system_id']})")

        hubs = reader.get_hubs()
        links = reader.get_links()
        satellites = reader.get_satellites()
        all_components = hubs + links + satellites

        default_logger.info(
            f"Found: {len(hubs)} hub(s), {len(links)} link(s), {len(satellites)} satellite(s)"
        )

        if self.dry_run:
            self._dry_run(all_components)
            return

        self._generate_sql(all_components)
        self._generate_yaml(all_components)

        default_logger.info(f"Generated {len(all_components)} components successfully")

    def _dry_run(self, components) -> None:
        default_logger.info("DRY RUN — generated SQL")

        for component in components:
            file_path = component.get_file_path(str(self.output_path))
            default_logger.info(f"{file_path}")
            default_logger.info(component.generate_sql())

    def _generate_sql(self, components) -> None:

        default_logger.info(f"Generating SQL models to {self.output_path}")

        generator = DVComponentManager(base_path=str(self.output_path))
        generator.generate_components(
            components,
            overwrite=self.overwrite,
        )

    def _generate_yaml(self, components) -> None:

        default_logger.info("Generating YAML metadata files")

        config_generator = DVConfigGenerator(project_path=str(self.output_path))

        yaml_paths = config_generator.generate_all_yaml(components)

        for path in yaml_paths:
            default_logger.info(str(path))


# ---------------------------------------------------------------------------
# Example usage
# ---------------------------------------------------------------------------


def example_usage():
    """Examples of using the generator in Databricks or Python."""

    # full generation
    MetadataModelGenerator().run()

    # dry run
    # MetadataModelGenerator(dry_run=True).run()

    # custom output
    # MetadataModelGenerator(output_path="/dbfs/tmp/models").run()

    # custom config
    # MetadataModelGenerator(config_path="/Workspace/config.yaml").run()
