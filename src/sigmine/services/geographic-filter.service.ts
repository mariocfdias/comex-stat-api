import { Injectable, Logger } from '@nestjs/common';
import type { FeatureCollection, Geometry, GeoJsonProperties, Feature, Polygon, MultiPolygon } from 'geojson';
import * as turf from '@turf/turf';
import * as fs from 'fs';
import * as path from 'path';

@Injectable()
export class GeographicFilterService {
  private readonly logger = new Logger(GeographicFilterService.name);
  private cearaGeometry: FeatureCollection | null = null;

  async getCearaGeometry(): Promise<FeatureCollection> {
    if (!this.cearaGeometry) {
      const cearaFilePath = path.resolve(
        process.cwd(),
        'static',
        'geojs-23-mun.json',
      );

      try {
        const cearaData = fs.readFileSync(cearaFilePath, 'utf-8');
        this.cearaGeometry = JSON.parse(cearaData) as FeatureCollection;
      } catch (error) {
        this.logger.error(
          `Failed to load Ceará geometry from ${cearaFilePath}`,
          (error as Error).stack,
        );
        throw new Error('Unable to load Ceará geographic boundaries');
      }
    }

    return this.cearaGeometry;
  }

  private createCearaBoundingPolygon(cearaGeometry: FeatureCollection): Feature<Polygon | MultiPolygon, GeoJsonProperties> {
    // Instead of combining all polygons (which is complex), create a bounding box for Ceará
    // This is more reliable and faster for intersection checks
    const bbox = turf.bbox(cearaGeometry);
    const bboxPolygon = turf.bboxPolygon(bbox);
    
    return bboxPolygon as Feature<Polygon | MultiPolygon, GeoJsonProperties>;
  }

  async filterByCearaBounds(
    geoJson: FeatureCollection<Geometry, GeoJsonProperties>,
  ): Promise<FeatureCollection<Geometry, GeoJsonProperties>> {
    try {
      const cearaGeometry = await this.getCearaGeometry();
      const cearaBounds = this.createCearaBoundingPolygon(cearaGeometry);

      const filteredFeatures = geoJson.features.filter((feature) => {
        try {
          // Validate feature geometry
          if (!feature || !feature.geometry || !feature.geometry.type) {
            return false;
          }

          // Only process polygon and multipolygon features
          if (feature.geometry.type !== 'Polygon' && feature.geometry.type !== 'MultiPolygon') {
            return false;
          }

          // Check if the feature intersects with Ceará bounds using bounding box overlap
          const featureBbox = turf.bbox(feature);
          const cearaBbox = turf.bbox(cearaBounds);
          
          // Simple bounding box overlap check
          const overlaps = !(
            featureBbox[2] < cearaBbox[0] || // feature east < ceara west
            featureBbox[0] > cearaBbox[2] || // feature west > ceara east
            featureBbox[3] < cearaBbox[1] || // feature north < ceara south
            featureBbox[1] > cearaBbox[3]    // feature south > ceara north
          );

          return overlaps;
        } catch (error) {
          this.logger.warn(
            `Failed to check intersection for feature: ${(error as Error).message}`,
          );
          return false;
        }
      });

      // For now, return the filtered features without clipping to avoid geometry issues
      // The bounding box filtering already removes most features outside Ceará
      return {
        type: 'FeatureCollection',
        features: filteredFeatures,
      };
    } catch (error) {
      this.logger.error(
        'Failed to filter by Ceará bounds',
        (error as Error).stack,
      );
      // Return original data if filtering fails
      return geoJson;
    }
  }
}