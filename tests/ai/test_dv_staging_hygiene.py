"""dv_components staging emitter: hashed-column rendering matches AutomateDV.

AutomateDV wants a business-key / PK hash as a plain column list and a hashdiff as
``{is_hashdiff: true, columns: [...]}``. Emitting the dict form for a non-hashdiff
makes AutomateDV warn ("use list syntax for PKs"); these tests lock the correct
shape so the warning cannot return.
"""

from __future__ import annotations

from dbt_builder.src.dv_components.pydantic_model.sql.staging import HashedColumns


def test_pk_hash_renders_as_plain_list():
    pk = HashedColumns(column_name="HK_TERMINAL", is_hashdiff=False, columns=["mrid"])
    assert pk.dv_model == {"HK_TERMINAL": ["mrid"]}


def test_composite_pk_hash_renders_as_plain_list():
    pk = HashedColumns(column_name="HK_LINK", is_hashdiff=False, columns=["a", "b"])
    assert pk.dv_model == {"HK_LINK": ["a", "b"]}


def test_hashdiff_renders_as_dict_with_flag():
    hd = HashedColumns(column_name="HD_DETAILS", is_hashdiff=True, columns=["name", "phases"])
    assert hd.dv_model == {"HD_DETAILS": {"is_hashdiff": True, "columns": ["name", "phases"]}}
