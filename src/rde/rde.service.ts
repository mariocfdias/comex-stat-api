import {
  BadRequestException,
  HttpException,
  HttpStatus,
  Inject,
  Injectable,
  Logger,
  ServiceUnavailableException,
} from '@nestjs/common';
import { CACHE_MANAGER } from '@nestjs/cache-manager';
import { AxiosError } from 'axios';
import type { AxiosInstance } from 'axios';
import type { Cache } from 'cache-manager';
import {
  RdeQueryDto,
  RdeODataResponse,
  TodosRegistrosDto,
  RegistrosIedDto,
} from './dto/rde.dto';

export const RDE_HTTP_CLIENT = Symbol('RDE_HTTP_CLIENT');

@Injectable()
export class RdeService {
  private readonly logger = new Logger(RdeService.name);
  private readonly cacheNamespace = 'rde';
  private readonly cacheTtlSeconds = 60 * 60 * 24; // 24 hours

  constructor(
    @Inject(RDE_HTTP_CLIENT) private readonly http: AxiosInstance,
    @Inject(CACHE_MANAGER) private readonly cache: Cache,
  ) {}

  async getTodosRegistros(
    query: RdeQueryDto,
  ): Promise<{ data: TodosRegistrosDto[]; total?: number }> {
    const cacheKey = this.buildCacheKey('todos-registros', query);

    return this.getCachedValue(cacheKey, async () => {
      const params = this.buildODataParams(query);

      try {
        const response = await this.http.get<
          RdeODataResponse<TodosRegistrosDto>
        >('/TodosRegistros', { params });

        return {
          data: response.data.value || [],
          total: response.data.value?.length,
        };
      } catch (error) {
        this.handleApiError(error, 'getTodosRegistros');
      }
    });
  }

  async getRegistrosIed(
    query: RdeQueryDto,
  ): Promise<{ data: RegistrosIedDto[]; total?: number }> {
    const cacheKey = this.buildCacheKey('registros-ied', query);

    return this.getCachedValue(cacheKey, async () => {
      const params = this.buildODataParams(query);

      try {
        const response = await this.http.get<RdeODataResponse<RegistrosIedDto>>(
          '/RegistrosIED',
          { params },
        );

        return {
          data: response.data.value || [],
          total: response.data.value?.length,
        };
      } catch (error) {
        this.handleApiError(error, 'getRegistrosIed');
      }
    });
  }

  private buildODataParams(query: RdeQueryDto): Record<string, string> {
    const params: Record<string, string> = {
      $format: 'json',
      $filter: "contains(UfPessoaNacional,'CE')",
      $orderby: 'Ano desc',
    };

    if (query.select) {
      params.$select = query.select;
    }

    if (query.skip !== undefined) {
      params.$skip = query.skip.toString();
    }

    if (query.top !== undefined) {
      params.$top = query.top.toString();
    }

    return params;
  }

  private buildCacheKey(segment: string, payload: unknown): string {
    return `${this.cacheNamespace}:${segment}:${this.serializeForCache(payload)}`;
  }

  private serializeForCache(value: unknown): string {
    const normalize = (input: unknown): unknown => {
      if (Array.isArray(input)) {
        return input.map((item) => normalize(item));
      }
      if (input && typeof input === 'object') {
        return Object.keys(input as Record<string, unknown>)
          .sort()
          .reduce(
            (acc, key) => {
              const normalizedValue = normalize(
                (input as Record<string, unknown>)[key],
              );
              if (normalizedValue !== undefined) {
                acc[key] = normalizedValue;
              }
              return acc;
            },
            {} as Record<string, unknown>,
          );
      }
      return input;
    };

    return JSON.stringify(normalize(value));
  }

  private async getCachedValue<T>(
    key: string,
    resolver: () => Promise<T>,
  ): Promise<T> {
    if (!this.cache) {
      return resolver();
    }

    const cached = await this.cache.get<T>(key);
    if (cached !== undefined) {
      return cached;
    }

    const value = await resolver();
    await this.cache.set(key, value, this.cacheTtlSeconds);
    return value;
  }

  private handleApiError(error: unknown, method: string): never {
    this.logger.error(
      `RDE API request failed in ${method}`,
      error instanceof Error ? error.stack : undefined,
      method,
    );

    if (error instanceof ServiceUnavailableException) {
      throw error;
    }

    if (error instanceof AxiosError && error.response) {
      const message =
        typeof error.response.data === 'string'
          ? error.response.data
          : (error.response.data?.message ?? 'RDE API request failed.');

      throw new HttpException(
        message,
        error.response.status ?? HttpStatus.BAD_GATEWAY,
        {
          cause: error,
        },
      );
    }

    throw new ServiceUnavailableException('Unable to reach RDE API.');
  }
}
