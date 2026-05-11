#!/usr/bin/env python3
"""Polygon-aware raster aggregation helpers for BOLD grid cells."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterio.features import rasterize
from rasterio.transform import Affine, from_origin
from shapely.geometry import box
import xarray as xr


ValidMask = Callable[[np.ndarray], np.ndarray]


@dataclass
class RasterCellMeanExtractor:
    """Rasterize cell polygons once for a raster grid, then aggregate by cell."""

    cells: gpd.GeoDataFrame
    transform: Affine
    shape: tuple[int, int]
    crs: object
    all_touched: bool = False

    def __post_init__(self) -> None:
        cells = self.cells
        if cells.crs is not None and self.crs is not None and cells.crs != self.crs:
            cells = cells.to_crs(self.crs)
        self.cells_reproj = cells.reset_index(drop=True)
        raster_bounds = rasterio.transform.array_bounds(self.shape[0], self.shape[1], self.transform)
        raster_box = box(*raster_bounds)
        shapes = (
            (geom, i + 1)
            for i, geom in enumerate(self.cells_reproj.geometry)
            if geom is not None and not geom.is_empty and geom.intersects(raster_box)
        )
        self.labels = rasterize(
            shapes,
            out_shape=self.shape,
            transform=self.transform,
            fill=0,
            dtype="int32",
            all_touched=self.all_touched,
        )

    def aggregate(self, values: np.ndarray, valid_mask: Optional[ValidMask] = None, fill_empty: float = np.nan) -> pd.Series:
        arr = np.asarray(values)
        if arr.shape != self.shape:
            raise ValueError(f"Raster shape {arr.shape} does not match label shape {self.shape}")

        valid = self.labels > 0
        if np.ma.isMaskedArray(arr):
            valid &= ~np.ma.getmaskarray(arr)
            arr = arr.filled(np.nan)
        valid &= np.isfinite(arr)
        if valid_mask is not None:
            valid &= valid_mask(arr)

        n_cells = len(self.cells_reproj)
        sums = np.bincount(self.labels[valid], weights=arr[valid], minlength=n_cells + 1)
        counts = np.bincount(self.labels[valid], minlength=n_cells + 1)
        out = np.full(n_cells, fill_empty, dtype="float64")
        has_data = counts[1:] > 0
        out[has_data] = sums[1:][has_data] / counts[1:][has_data]
        return pd.Series(out, index=self.cells.index)


def aggregate_raster_file(
    raster_path: Path,
    cells: gpd.GeoDataFrame,
    valid_mask: Optional[ValidMask] = None,
    fill_empty: float = np.nan,
    all_touched: bool = False,
) -> pd.Series:
    """Aggregate a raster file to cell means using polygon rasterization."""
    with rasterio.open(raster_path) as src:
        data = src.read(1, masked=True)
        extractor = RasterCellMeanExtractor(
            cells=cells,
            transform=src.transform,
            shape=(src.height, src.width),
            crs=src.crs,
            all_touched=all_touched,
        )
        return extractor.aggregate(data, valid_mask=valid_mask, fill_empty=fill_empty)


class XarrayCellMeanExtractor:
    """Cell mean extractor for regular lon/lat xarray rasters."""

    def __init__(self, cells: gpd.GeoDataFrame, all_touched: bool = False) -> None:
        self.cells = cells
        self.all_touched = all_touched
        self._cache: dict[tuple[int, int, float, float, float, float], RasterCellMeanExtractor] = {}

    @staticmethod
    def _coord_name(da: xr.DataArray, names: tuple[str, ...]) -> str:
        for name in names:
            if name in da.coords:
                return name
        raise KeyError(f"Could not find coordinate among {names}")

    @staticmethod
    def _as_top_to_bottom(da: xr.DataArray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        lon_name = XarrayCellMeanExtractor._coord_name(da, ("lon", "longitude", "x"))
        lat_name = XarrayCellMeanExtractor._coord_name(da, ("lat", "latitude", "y"))
        squeezed = da.squeeze(drop=True)
        values = np.asarray(squeezed.values)
        lon = np.asarray(squeezed[lon_name].values)
        lat = np.asarray(squeezed[lat_name].values)
        if values.ndim != 2:
            raise ValueError(f"Expected 2D raster after squeeze, got shape {values.shape}")
        if lat[0] < lat[-1]:
            values = np.flipud(values)
            lat = lat[::-1]
        return values, lon, lat

    def _extractor_for(self, da: xr.DataArray) -> tuple[RasterCellMeanExtractor, np.ndarray]:
        values, lon, lat = self._as_top_to_bottom(da)
        xres = float(abs(np.nanmedian(np.diff(lon))))
        yres = float(abs(np.nanmedian(np.diff(lat))))
        west = float(np.nanmin(lon) - xres / 2)
        north = float(np.nanmax(lat) + yres / 2)
        transform = from_origin(west, north, xres, yres)
        key = (values.shape[0], values.shape[1], round(west, 10), round(north, 10), round(xres, 12), round(yres, 12))
        if key not in self._cache:
            self._cache[key] = RasterCellMeanExtractor(
                cells=self.cells,
                transform=transform,
                shape=values.shape,
                crs="EPSG:4326",
                all_touched=self.all_touched,
            )
        return self._cache[key], values

    def aggregate(self, da: xr.DataArray, valid_mask: Optional[ValidMask] = None, fill_empty: float = np.nan) -> pd.Series:
        extractor, values = self._extractor_for(da)
        return extractor.aggregate(values, valid_mask=valid_mask, fill_empty=fill_empty)
