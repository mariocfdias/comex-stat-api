import {
  AggregationLevel,
  NationalComparisonDto,
  PeriodDto,
  PartnerCountryDto,
  ProductDto,
  SummaryDataDto,
  SummaryPeriod,
  TimeSeriesDataDto,
  TimeSeriesPeriodicity,
  TimeSeriesSeries,
  TradeFlow,
} from './dto/comexstat.dto';
import { CACHE_MANAGER } from '@nestjs/cache-manager';
import {
  BadRequestException,
  HttpException,
  HttpStatus,
  Inject,
  Injectable,
  Logger,
  ServiceUnavailableException,
} from '@nestjs/common';
import { AxiosError } from 'axios';
import type { AxiosInstance } from 'axios';
import type { Cache } from 'cache-manager';

interface Period {
  from: string;
  to: string;
}

interface Filter {
  filter: string;
  values: (string | number)[];
}

interface GeneralQueryParams {
  flow: TradeFlow.EXPORT | TradeFlow.IMPORT;
  monthDetail: boolean;
  period: Period;
  filters?: Filter[];
  details?: string[];
  metrics?: string[];
}

interface ComexStatResponse {
  data: {
    list: any[];
  };
  success: boolean;
  message: string | null;
}

export const COMEXSTAT_HTTP_CLIENT = Symbol('COMEXSTAT_HTTP_CLIENT');

@Injectable()
export class ComexstatService {
  private readonly logger = new Logger(ComexstatService.name);
  private readonly CEARA_STATE_ID = 23;
  private readonly cacheNamespace = 'comexstat';
  private readonly cacheTtlSeconds = 60 * 60 * 24;

  constructor(
    @Inject(COMEXSTAT_HTTP_CLIENT) private readonly http: AxiosInstance,
    @Inject(CACHE_MANAGER) private readonly cache: Cache,
  ) {}

  async getSummaryData(
    periodType: SummaryPeriod,
    customPeriod?: PeriodDto,
  ): Promise<SummaryDataDto> {
    const cacheKey = this.buildCacheKey('summary', { periodType, customPeriod });

    return this.getCachedValue(cacheKey, async () => {
      const { currentYear, currentMonth, previousMonth, previousMonthYear } =
        this.getCurrentDateInfo();

      let period: Period;
      let periodLabel: string;

      switch (periodType) {
        case SummaryPeriod.CURRENT_MONTH:
          period = {
            from: this.formatPeriod(previousMonthYear, previousMonth),
            to: this.formatPeriod(previousMonthYear, previousMonth),
          };
          periodLabel = `${this.formatMonthAbbreviation(previousMonth)}/${previousMonthYear}`;
          break;

        case SummaryPeriod.YEAR_TO_DATE:
          period = {
            from: this.formatPeriod(currentYear, 1),
            to: this.formatPeriod(currentYear, currentMonth),
          };
          periodLabel = `Jan-${this.formatMonthAbbreviation(currentMonth)}/${currentYear}`;
          break;

        case SummaryPeriod.LAST_YEAR:
          period = {
            from: this.formatPeriod(currentYear - 1, 1),
            to: this.formatPeriod(currentYear - 1, 12),
          };
          periodLabel = `${currentYear - 1}`;
          break;

        case SummaryPeriod.CUSTOM:
          if (!customPeriod) {
            throw new BadRequestException('Custom period is required when period type is custom.');
          }
          period = customPeriod;
          periodLabel = `${customPeriod.from} - ${customPeriod.to}`;
          break;

        default:
          throw new BadRequestException('Unsupported period type.');
      }

      const [exportResponse, importResponse] = await Promise.all([
        this.queryGeneral({
          flow: TradeFlow.EXPORT,
          monthDetail: false,
          period,
          filters: [{ filter: 'state', values: [this.CEARA_STATE_ID] }],
          metrics: ['metricFOB'],
        }),
        this.queryGeneral({
          flow: TradeFlow.IMPORT,
          monthDetail: false,
          period,
          filters: [{ filter: 'state', values: [this.CEARA_STATE_ID] }],
          metrics: ['metricFOB', 'metricCIF'],
        }),
      ]);

      const exportsValue = this.toMillions(exportResponse.data.list[0]?.metricFOB ?? 0);
      const importsValue = this.toMillions(importResponse.data.list[0]?.metricFOB ?? 0);

      return {
        period: periodLabel,
        exports: exportsValue,
        imports: importsValue,
        tradeBalance: exportsValue - importsValue,
        tradeCurrent: exportsValue + importsValue,
      };
    });
  }

  async getTimeSeries(
    periodicity: TimeSeriesPeriodicity,
    series: TimeSeriesSeries,
    startYear: number,
    endYear?: number,
    includeSectors = false,
  ): Promise<TimeSeriesDataDto[]> {
    const cacheKey = this.buildCacheKey('timeseries', {
      periodicity,
      series,
      startYear,
      endYear,
      includeSectors,
    });

    return this.getCachedValue(cacheKey, async () => {
      const { currentYear } = this.getCurrentDateInfo();
      const effectiveEndYear = endYear ?? currentYear;

      const period: Period = {
        from: this.formatPeriod(startYear, 1),
        to: this.formatPeriod(effectiveEndYear, 12),
      };

      const monthDetail = periodicity === TimeSeriesPeriodicity.MONTHLY;
      const details = includeSectors ? ['ISICSection'] : [];

      const requests: Array<{
        kind: TradeFlow.EXPORT | TradeFlow.IMPORT;
        response: Promise<ComexStatResponse>;
      }> = [];

      if (
        series === TimeSeriesSeries.EXPORT ||
        series === TimeSeriesSeries.CURRENT ||
        series === TimeSeriesSeries.BALANCE
      ) {
        requests.push({
          kind: TradeFlow.EXPORT,
          response: this.queryGeneral({
            flow: TradeFlow.EXPORT,
            monthDetail,
            period,
            filters: [{ filter: 'state', values: [this.CEARA_STATE_ID] }],
            details,
            metrics: ['metricFOB'],
          }),
        });
      }

      if (
        series === TimeSeriesSeries.IMPORT ||
        series === TimeSeriesSeries.CURRENT ||
        series === TimeSeriesSeries.BALANCE
      ) {
        requests.push({
          kind: TradeFlow.IMPORT,
          response: this.queryGeneral({
            flow: TradeFlow.IMPORT,
            monthDetail,
            period,
            filters: [{ filter: 'state', values: [this.CEARA_STATE_ID] }],
            details,
            metrics: ['metricFOB'],
          }),
        });
      }

      const responses = await Promise.all(requests.map(({ response }) => response));
      const dataMap = new Map<string, TimeSeriesDataDto>();

      responses.forEach((response, index) => {
        const kind = requests[index].kind;
        response.data.list.forEach((item) => {
          const monthNumberRaw = item.monthNumber ?? item.month;
          const monthNumber = Number(monthNumberRaw);
          const monthKey =
            monthDetail && Number.isFinite(monthNumber)
              ? String(monthNumber).padStart(2, '0')
              : undefined;
          const key =
            monthDetail && monthKey ? `${item.year}-${monthKey}` : String(item.year);

          if (!dataMap.has(key)) {
            dataMap.set(key, {
              period: key,
              year: String(item.year),
              month: monthKey,
            });
          }

          const record = dataMap.get(key)!;
          const value = this.toMillions(item.metricFOB);

          if (kind === TradeFlow.EXPORT) {
            record.exports = value;
          } else if (kind === TradeFlow.IMPORT) {
            record.imports = value;
          }

          if (includeSectors && item.ISICSection) {
            const sectors = record.sectors ?? [];
            const rawCode = item.coIsicSection ?? item.ISICSectionCode;
            sectors.push({
              code: rawCode !== undefined ? String(rawCode) : '',
              name: item.ISICSection,
              value,
            });
            record.sectors = sectors;
          }
        });
      });

      const results = Array.from(dataMap.values());

      results.forEach((item) => {
        if (
          series === TimeSeriesSeries.CURRENT &&
          item.exports !== undefined &&
          item.imports !== undefined
        ) {
          item.current = item.exports + item.imports;
        }
        if (
          series === TimeSeriesSeries.BALANCE &&
          item.exports !== undefined &&
          item.imports !== undefined
        ) {
          item.balance = item.exports - item.imports;
        }
      });

      results.sort((a, b) => a.period.localeCompare(b.period));

      return results;
    });
  }

  async getPartnerCountries(
    flow: TradeFlow,
    periodType: SummaryPeriod,
    customPeriod?: PeriodDto,
    topN = 10,
  ): Promise<PartnerCountryDto[]> {
    const cacheKey = this.buildCacheKey('partners', {
      flow,
      periodType,
      customPeriod,
      topN,
    });

    return this.getCachedValue(cacheKey, async () => {
      const { currentYear, currentMonth, previousMonth, previousMonthYear } =
        this.getCurrentDateInfo();

      let period: Period;

      switch (periodType) {
        case SummaryPeriod.CURRENT_MONTH:
          period = {
            from: this.formatPeriod(previousMonthYear, previousMonth),
            to: this.formatPeriod(previousMonthYear, previousMonth),
          };
          break;
        case SummaryPeriod.YEAR_TO_DATE:
          period = {
            from: this.formatPeriod(currentYear, 1),
            to: this.formatPeriod(currentYear, currentMonth),
          };
          break;
        case SummaryPeriod.CUSTOM:
          if (!customPeriod) {
            throw new BadRequestException('Custom period is required when period type is custom.');
          }
          period = customPeriod;
          break;
        default:
          throw new BadRequestException('Unsupported period type.');
      }

      const requests: Array<{
        kind: TradeFlow.EXPORT | TradeFlow.IMPORT;
        response: Promise<ComexStatResponse>;
      }> = [];

      if (flow === TradeFlow.EXPORT || flow === TradeFlow.CURRENT) {
        requests.push({
          kind: TradeFlow.EXPORT,
          response: this.queryGeneral({
            flow: TradeFlow.EXPORT,
            monthDetail: false,
            period,
            filters: [{ filter: 'state', values: [this.CEARA_STATE_ID] }],
            details: ['country'],
            metrics: ['metricFOB'],
          }),
        });
      }

      if (flow === TradeFlow.IMPORT || flow === TradeFlow.CURRENT) {
        requests.push({
          kind: TradeFlow.IMPORT,
          response: this.queryGeneral({
            flow: TradeFlow.IMPORT,
            monthDetail: false,
            period,
            filters: [{ filter: 'state', values: [this.CEARA_STATE_ID] }],
            details: ['country'],
            metrics: ['metricFOB'],
          }),
        });
      }

      const responses = await Promise.all(requests.map(({ response }) => response));
      const countryMap = new Map<string, PartnerCountryDto>();

      responses.forEach((response, index) => {
        const kind = requests[index].kind;

        response.data.list.forEach((item) => {
          const countryName = item.country ?? item.countryName;
          if (!countryName) {
            return;
          }

          if (!countryMap.has(countryName)) {
            countryMap.set(countryName, { country: countryName });
          }

          const record = countryMap.get(countryName)!;
          const value = this.toMillions(item.metricFOB);

          if (kind === TradeFlow.EXPORT) {
            record.exports = value;
          } else if (kind === TradeFlow.IMPORT) {
            record.imports = value;
          }
        });
      });

      const results = Array.from(countryMap.values());
      let total = 0;

      results.forEach((item) => {
        if (flow === TradeFlow.CURRENT) {
          item.current = (item.exports ?? 0) + (item.imports ?? 0);
          total += item.current;
        } else if (flow === TradeFlow.EXPORT) {
          total += item.exports ?? 0;
        } else {
          total += item.imports ?? 0;
        }

        item.balance = (item.exports ?? 0) - (item.imports ?? 0);
      });

      results.forEach((item) => {
        const base =
          flow === TradeFlow.EXPORT
            ? item.exports
            : flow === TradeFlow.IMPORT
              ? item.imports
              : item.current;

        item.percentage = total > 0 && base !== undefined ? (base / total) * 100 : 0;
      });

      const sortKey =
        flow === TradeFlow.EXPORT
          ? 'exports'
          : flow === TradeFlow.IMPORT
            ? 'imports'
            : 'current';

      results.sort((a, b) => (b[sortKey] ?? 0) - (a[sortKey] ?? 0));

      return results.slice(0, topN);
    });
  }

  async getTopProducts(
    flow: TradeFlow.EXPORT | TradeFlow.IMPORT,
    periodicity: TimeSeriesPeriodicity,
    period: PeriodDto | number | undefined,
    aggregation: AggregationLevel,
    topN = 20,
  ): Promise<ProductDto[]> {
    const cacheKey = this.buildCacheKey('products', {
      flow,
      periodicity,
      period: typeof period === 'number' || period === undefined ? period : { ...period },
      aggregation,
      topN,
    });

    return this.getCachedValue(cacheKey, async () => {
      const periodOrYear = period ?? this.getCurrentDateInfo().currentYear - 1;
      let queryPeriod: Period;

      if (typeof periodOrYear === 'number') {
        queryPeriod = {
          from: this.formatPeriod(periodOrYear, 1),
          to: this.formatPeriod(periodOrYear, 12),
        };
      } else {
        queryPeriod = periodOrYear;
      }

      const monthDetail = periodicity === TimeSeriesPeriodicity.MONTHLY;

      const response = await this.queryGeneral({
        flow,
        monthDetail,
        period: queryPeriod,
        filters: [{ filter: 'state', values: [this.CEARA_STATE_ID] }],
        details: [aggregation],
        metrics: ['metricFOB', 'metricKG'],
      });

      const fieldMap: Record<AggregationLevel, { code: string; desc: string }> = {
        [AggregationLevel.NCM]: { code: 'ncmCode', desc: 'ncm' },
        [AggregationLevel.HEADING]: { code: 'headingCode', desc: 'heading' },
        [AggregationLevel.CHAPTER]: { code: 'chapterCode', desc: 'chapter' },
      };

      const fields = fieldMap[aggregation];
      const products: ProductDto[] = [];
      let totalValue = 0;

      response.data.list.forEach((item) => {
        const value = this.toMillions(item.metricFOB);
        const weight = item.metricKG ? Number(item.metricKG) : undefined;

        products.push({
          code: String(item[fields.code] ?? ''),
          description: item[fields.desc] ?? '',
          value,
          weight: Number.isFinite(weight) ? weight : undefined,
          quantity: undefined,
          percentage: 0,
        });

        totalValue += value;
      });

      products.forEach((product) => {
        product.percentage = totalValue > 0 ? (product.value / totalValue) * 100 : 0;
      });

      products.sort((a, b) => b.value - a.value);

      return products.slice(0, topN);
    });
  }

  async getNationalComparison(
    flow: TradeFlow.EXPORT | TradeFlow.IMPORT,
    period: PeriodDto,
  ): Promise<NationalComparisonDto> {
    const cacheKey = this.buildCacheKey('national-comparison', {
      flow,
      period,
    });

    return this.getCachedValue(cacheKey, async () => {
      const [nationalResponse, cearaResponse, statesResponse] = await Promise.all([
        this.queryGeneral({
          flow,
          monthDetail: false,
          period,
          metrics: ['metricFOB'],
        }),
        this.queryGeneral({
          flow,
          monthDetail: false,
          period,
          filters: [{ filter: 'state', values: [this.CEARA_STATE_ID] }],
          metrics: ['metricFOB'],
        }),
        this.queryGeneral({
          flow,
          monthDetail: false,
          period,
          details: ['state'],
          metrics: ['metricFOB'],
        }),
      ]);

      const nationalTotal = Number(nationalResponse.data.list[0]?.metricFOB ?? 0);
      const cearaTotal = Number(cearaResponse.data.list[0]?.metricFOB ?? 0);

      const participation =
        nationalTotal > 0 ? (cearaTotal / nationalTotal) * 100 : 0;

      const states = statesResponse.data.list
        .map((item) => ({
          state: item.state ?? item.stateName,
          value: Number(item.metricFOB ?? 0),
        }))
        .sort((a, b) => b.value - a.value);

      const rankingIndex = states.findIndex((state) => state.state === 'Ceará');
      const ranking = rankingIndex >= 0 ? rankingIndex + 1 : 0;

      return { participation, ranking };
    });
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
          .reduce((acc, key) => {
            const normalizedValue = normalize(
              (input as Record<string, unknown>)[key],
            );
            if (normalizedValue !== undefined) {
              acc[key] = normalizedValue;
            }
            return acc;
          }, {} as Record<string, unknown>);
      }
      return input;
    };

    return JSON.stringify(normalize(value));
  }

  private async getCachedValue<T>(key: string, resolver: () => Promise<T>): Promise<T> {
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

  private formatPeriod(year: number, month?: number): string {
    if (month) {
      const paddedMonth = String(month).padStart(2, '0');
      return `${year}-${paddedMonth}`;
    }

    return `${year}-01`;
  }

  private getCurrentDateInfo(): {
    currentYear: number;
    currentMonth: number;
    previousMonth: number;
    previousMonthYear: number;
  } {
    const now = new Date();
    const reference = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), 1));
    reference.setUTCMonth(reference.getUTCMonth() - 2);

    const currentYear = reference.getUTCFullYear();
    const currentMonth = reference.getUTCMonth() + 1;

    const previousDate = new Date(reference);
    previousDate.setUTCMonth(previousDate.getUTCMonth() - 1);

    return {
      currentYear,
      currentMonth,
      previousMonth: previousDate.getUTCMonth() + 1,
      previousMonthYear: previousDate.getUTCFullYear(),
    };
  }

  private formatMonthAbbreviation(month: number): string {
    const date = new Date(Date.UTC(2000, month - 1, 1));
    return new Intl.DateTimeFormat('pt-BR', { month: 'short' })
      .format(date)
      .replace('.', '')
      .trim();
  }

  private toMillions(value: unknown): number {
    const numericValue =
      typeof value === 'string' ? Number(value.replace(',', '.')) : Number(value);

    if (!Number.isFinite(numericValue)) {
      return 0;
    }

    return numericValue / 1_000_000;
  }

  private async queryGeneral(params: GeneralQueryParams): Promise<ComexStatResponse> {
    try {
      const response = await this.http.post<ComexStatResponse>('/general', params, {
        params: { language: 'pt' },
      });

      if (!response.data?.success) {
        throw new ServiceUnavailableException(
          response.data?.message ?? 'ComexStat API request failed.',
        );
      }

      return response.data;
    } catch (error) {
      this.logger.error(
        'ComexStat API request failed',
        error instanceof Error ? error.stack : undefined,
        'queryGeneral',
      );

      if (error instanceof ServiceUnavailableException) {
        throw error;
      }

      if (error instanceof AxiosError && error.response) {
        const message =
          typeof error.response.data === 'string'
            ? error.response.data
            : error.response.data?.message ?? 'ComexStat API request failed.';

        throw new HttpException(message, error.response.status ?? HttpStatus.BAD_GATEWAY, {
          cause: error,
        });
      }

      throw new ServiceUnavailableException('Unable to reach ComexStat API.');
    }
  }
}
