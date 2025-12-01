import { CACHE_MANAGER } from '@nestjs/cache-manager';
import {
  Inject,
  Injectable,
  Logger,
  NotFoundException,
  ServiceUnavailableException,
} from '@nestjs/common';
import type { Cache } from 'cache-manager';
import path from 'path';
import * as shapefile from 'shapefile';
import {
  SIGMINE_LAYER_SHAPEFILES,
  SigmineLayer,
  type LayerGeoJsonDto,
} from './dto/sigmine-layer.dto';

@Injectable()
export class SigmineService {
  private readonly logger = new Logger(SigmineService.name);
  private readonly cachePrefix = 'sigmine:layer';
  private readonly cacheTtlSeconds = 60 * 60 * 24;

  constructor(
    @Inject(CACHE_MANAGER) private readonly cache: Cache,
  ) {}

  async getLayer(layer: SigmineLayer): Promise<LayerGeoJsonDto> {
    const shapefilePath = SIGMINE_LAYER_SHAPEFILES[layer];
    if (!shapefilePath) {
      throw new NotFoundException('Layer not configured.');
    }

    const cacheKey = `${this.cachePrefix}:${layer}`;
    const cached = await this.cache.get<LayerGeoJsonDto>(cacheKey);
    if (cached) {
      return cached;
    }

    const shpFullPath = path.resolve(
      process.cwd(),
      'static',
      shapefilePath,
    );

    try {
      const geoJson = (await shapefile.read(shpFullPath)) as LayerGeoJsonDto;
      await this.cache.set(cacheKey, geoJson, this.cacheTtlSeconds);
      return geoJson;
    } catch (error) {
      const maybeErrno = error as NodeJS.ErrnoException;
      if (maybeErrno?.code === 'ENOENT') {
        throw new NotFoundException(
          `Layer file for ${layer} not found at ${shpFullPath}.`,
        );
      }

      this.logger.error(
        `Failed to read shapefile for layer ${layer} at ${shpFullPath}`,
        (error as Error).stack,
      );
      throw new ServiceUnavailableException(
        'Unable to process shapefile. Please try again later.',
      );
    }
  }
}
