"""FFmpeg filter graph: SadTalker clip as a floating talking head."""

# Each segment: (main_start_s, main_end_s, clip_offset_s in SadTalker source)
TalkingSegment = tuple[float, float, float]


def _face_preprocess(stream: str, label: str) -> str:
    """Scale/crop SadTalker or portrait into a soft oval RGBA cutout."""
    return (
        f"[{stream}]scale=512:512:force_original_aspect_ratio=increase,"
        "crop=400:400,"
        "format=rgba,"
        "geq=r='r(X,Y)':g='g(X,Y)':b='b(X,Y)':"
        "a='if(lt(hypot(X-W/2,Y-H/2),W*0.38),255,"
        "if(lt(hypot(X-W/2,Y-H/2),W*0.46),"
        "255*(W*0.46-hypot(X-W/2,Y-H/2))/(W*0.08),0))'"
        f"[{label}]"
    )


def _overlay_pos(placement: str) -> str:
    if placement == "center":
        return "(W-w)/2:H-h-220"
    return "W-w-100:H-h-140"


def floating_avatar_filter(
    *,
    face_stream: str,
    placement: str = "corner",
    enable_between: tuple[float, float] | None = None,
) -> str:
    """Tight oval face cutout; optional time window (UI-relative seconds)."""
    pos = _overlay_pos(placement)

    enable = ""
    if enable_between is not None:
        start, end = enable_between
        enable = f":enable='between(t,{start},{end})'"

    return (
        "[0:v]scale=1920:1080:force_original_aspect_ratio=decrease,"
        "pad=1920:1080:(ow-iw)/2:(oh-ih)/2:black[bg];"
        + _face_preprocess(face_stream, "face")
        + ";"
        f"[bg][face]overlay={pos}{enable}:eof_action=pass[vid]"
    )


def floating_avatar_static_talking_filter(
    *,
    portrait_stream: str,
    talking_stream: str,
    talking_segments: list[TalkingSegment],
    placement: str = "corner",
) -> str:
    """Static portrait always visible; SadTalker lips per speech segment on main timeline."""
    pos = _overlay_pos(placement)
    n = len(talking_segments)

    parts: list[str] = [
        "[0:v]scale=1920:1080:force_original_aspect_ratio=decrease,"
        "pad=1920:1080:(ow-iw)/2:(oh-ih)/2:black[bg];",
        _face_preprocess(portrait_stream, "face_static") + ";",
    ]

    if n > 1:
        split_labels = [f"t{i}" for i in range(n)]
        parts.append(
            f"[{talking_stream}]split={n}"
            + "".join(f"[{label}]" for label in split_labels)
            + ";"
        )
    else:
        split_labels = [talking_stream]

    face_labels: list[tuple[str, float, float]] = []
    for i, (main_start, main_end, clip_offset) in enumerate(talking_segments):
        seg_dur = main_end - main_start
        raw = f"seg{i}raw"
        face = f"face_talk{i}"
        parts.append(
            f"[{split_labels[i]}]trim=start={clip_offset}:duration={seg_dur},"
            f"setpts=PTS-STARTPTS+{main_start}/TB[{raw}];"
            + _face_preprocess(raw, face)
            + ";"
        )
        face_labels.append((face, main_start, main_end))

    parts.append(f"[bg][face_static]overlay={pos}[bg_face];")
    cur = "bg_face"
    for i, (face, main_start, main_end) in enumerate(face_labels):
        out = "vid" if i == len(face_labels) - 1 else f"bg_talk{i}"
        parts.append(
            f"[{cur}][{face}]overlay={pos}:enable='between(t,{main_start},{main_end})'"
            f":eof_action=pass[{out}];"
        )
        cur = out

    return "".join(parts).rstrip(";")


def floating_avatar_static_talking_filter_legacy(
    *,
    portrait_stream: str,
    talking_stream: str,
    talking_window: tuple[float, float],
    placement: str = "corner",
) -> str:
    """Single-window wrapper (trim + PTS shift so overlay PTS matches main time)."""
    talk_start, talk_end = talking_window
    return floating_avatar_static_talking_filter(
        portrait_stream=portrait_stream,
        talking_stream=talking_stream,
        talking_segments=[(talk_start, talk_end, 0.0)],
        placement=placement,
    )
