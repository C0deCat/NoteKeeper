"""Media inspection use-case group builder."""

from notekeeper.application import (
    InspectAudioMetadata,
    InspectLocalAudioFile,
    MediaUseCases,
)

from .wiring_context import UseCaseWiringContext


def build_media_use_cases(context: UseCaseWiringContext) -> MediaUseCases:
    return MediaUseCases(
        inspect_metadata=InspectAudioMetadata(context.services.metadata_reader),
        inspect_local_file=InspectLocalAudioFile(
            context.services.source_metadata_reader
        ),
    )


__all__ = ["build_media_use_cases"]
