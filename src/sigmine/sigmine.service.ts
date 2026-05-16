import { CACHE_MANAGER } from '@nestjs/cache-manager';
import { Inject, Injectable, Logger, NotFoundException } from '@nestjs/common';
import { InjectRepository } from '@nestjs/typeorm';
import { Repository } from 'typeorm';
import type { Cache } from 'cache-manager';
import { SigmineLayer, type LayerGeoJsonDto } from './dto/sigmine-layer.dto';
import { SigmineLayerEntity } from './entities/sigmine-layer.entity';

@Injectable()
export class SigmineService {
  private readonly logger = new Logger(SigmineService.name);
  private readonly cachePrefix = 'sigmine:layer';
  private readonly cacheTtlSeconds = 60 * 60 * 24;

  constructor(
    @Inject(CACHE_MANAGER) private readonly cache: Cache,
    @InjectRepository(SigmineLayerEntity)
    private readonly layerRepo: Repository<SigmineLayerEntity>,
  ) {}

  async getLayer(layer: SigmineLayer): Promise<LayerGeoJsonDto> {
    const cacheKey = `${this.cachePrefix}:${layer}`;
    const cached = await this.cache.get<LayerGeoJsonDto>(cacheKey);
    if (cached) return cached;

    const row = await this.layerRepo.findOne({ where: { layerName: layer } });
    if (!row) {
      throw new NotFoundException(
        `Layer '${layer}' not found. Run the sigmine_ingest DAG to populate it.`,
      );
    }

    const geoJson = row.geojson as LayerGeoJsonDto;
    await this.cache.set(cacheKey, geoJson, this.cacheTtlSeconds);
    this.logger.log(`Layer ${layer} served from PostgreSQL (${row.featureCount} features)`);
    return geoJson;
  }
}
