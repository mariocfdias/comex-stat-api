import {
  AggregationLevel,
  NationalComparisonDto,
  StateRankingItemDto,
  StateRankingSectorDto,
  StateRankingPartnerDto,
  StateRankingProductDto,
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
import {
  Period,
  PeriodStrategyFactory,
} from './strategies/period.strategy';
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
          throw new BadRequestException(
            'Custom period is required when period type is custom.',
          );
        }
        period = customPeriod;
        periodLabel = `${customPeriod.from} - ${customPeriod.to}`;
        break;

      default:
        throw new BadRequestException('Unsupported period type.');
    }

    const cacheKey = this.buildCacheKey('summary', {
      period,
    });

    return this.getCachedValue(cacheKey, async () => {

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

      const exportsValue = this.toMillions(
        exportResponse.data.list[0]?.metricFOB ?? 0,
      );
      const importsValue = this.toMillions(
        importResponse.data.list[0]?.metricFOB ?? 0,
      );

      return {
        period: periodLabel,
        exports: exportsValue,
        imports: importsValue,
        tradeBalance: exportsValue - importsValue,
        tradeCurrent: exportsValue + importsValue,
      };
    });
  }

  async getSummaryHistory(period: PeriodDto): Promise<SummaryDataDto[]> {
    const monthRange = this.generateMonthsRange(period);

    if (monthRange.length === 0) {
      throw new BadRequestException(
        'É necessário informar um intervalo de meses válido.',
      );
    }

    const cacheKey = this.buildCacheKey('summary-history', period);

    return this.getCachedValue(cacheKey, async () => {
      const requestedKeys = new Set(monthRange.map((month) => month.key));
      const monthMap = new Map<string, SummaryDataDto>();

      monthRange.forEach(({ key, year, month }) => {
        monthMap.set(key, {
          period: `${this.formatMonthAbbreviation(month)}/${year}`,
          exports: 0,
          imports: 0,
          tradeBalance: 0,
          tradeCurrent: 0,
        });
      });

      const queryPeriod = {
        from: this.formatPeriod(monthRange[0].year, monthRange[0].month),
        to: this.formatPeriod(
          monthRange[monthRange.length - 1].year,
          monthRange[monthRange.length - 1].month,
        ),
      };

      const [exportResponse, importResponse] = await Promise.all([
        this.queryGeneral({
          flow: TradeFlow.EXPORT,
          monthDetail: true,
          period: queryPeriod,
          filters: [{ filter: 'state', values: [this.CEARA_STATE_ID] }],
          metrics: ['metricFOB'],
        }),
        this.queryGeneral({
          flow: TradeFlow.IMPORT,
          monthDetail: true,
          period: queryPeriod,
          filters: [{ filter: 'state', values: [this.CEARA_STATE_ID] }],
          metrics: ['metricFOB', 'metricCIF'],
        }),
      ]);

      const handleResponse = (
        response: ComexStatResponse,
        kind: TradeFlow.EXPORT | TradeFlow.IMPORT,
      ) => {
        response.data.list.forEach((item) => {
          const monthNumberRaw = item.monthNumber ?? item.month;
          const monthNumber = Number(monthNumberRaw);
          const year = Number(item.year);

          if (!Number.isFinite(monthNumber) || !Number.isFinite(year)) {
            return;
          }

          const key = `${year}-${String(monthNumber).padStart(2, '0')}`;
          if (!requestedKeys.has(key)) {
            return;
          }

          const record = monthMap.get(key);
          if (!record) {
            return;
          }

          const value = this.toMillions(item.metricFOB);

          if (kind === TradeFlow.EXPORT) {
            record.exports = value;
          } else {
            record.imports = value;
          }
        });
      };

      handleResponse(exportResponse, TradeFlow.EXPORT);
      handleResponse(importResponse, TradeFlow.IMPORT);

      monthRange.forEach(({ key }) => {
        const record = monthMap.get(key);
        if (!record) {
          return;
        }

        record.tradeBalance = (record.exports ?? 0) - (record.imports ?? 0);
        record.tradeCurrent = (record.exports ?? 0) + (record.imports ?? 0);
      });

      return monthRange.map(({ key }) => {
        const record = monthMap.get(key)!;
        const [year, month] = key.split('-');
        record.period = `${this.formatMonthAbbreviation(Number(month))}/${year}`;
        return record;
      });
    });
  }

  async getTimeSeries(
    periodicity: TimeSeriesPeriodicity,
    series: TimeSeriesSeries,
    startYear: number,
    endYear?: number,
    includeSectors = false,
  ): Promise<TimeSeriesDataDto[]> {
    const { currentYear } = this.getCurrentDateInfo();
    const effectiveEndYear = endYear ?? currentYear;

    const cacheKey = this.buildCacheKey('timeseries', {
      periodicity,
      series,
      startYear,
      endYear: effectiveEndYear,
      includeSectors,
    });

    return this.getCachedValue(cacheKey, async () => {

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

      const responses = await Promise.all(
        requests.map(({ response }) => response),
      );
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
            monthDetail && monthKey
              ? `${item.year}-${monthKey}`
              : String(item.year);

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
      case SummaryPeriod.LAST_YEAR:
        period = {
          from: this.formatPeriod(currentYear - 1, 1),
          to: this.formatPeriod(currentYear - 1, 12),
        };
        break;
      case SummaryPeriod.CUSTOM:
        if (!customPeriod) {
          throw new BadRequestException(
            'Custom period is required when period type is custom.',
          );
        }
        period = customPeriod;
        break;
      default:
        throw new BadRequestException('Unsupported period type.');
    }

    const cacheKey = this.buildCacheKey('partners', {
      flow,
      period,
      topN,
    });

    return this.getCachedValue(cacheKey, async () => {

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

      const responses = await Promise.all(
        requests.map(({ response }) => response),
      );
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

        item.percentage =
          total > 0 && base !== undefined ? (base / total) * 100 : 0;
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
    this.logger.debug(
      `getTopProducts chamado com period: ${JSON.stringify(period)}, periodicity: ${periodicity}`,
    );

    // Use Strategy pattern to handle period resolution
    const strategy = PeriodStrategyFactory.create(periodicity);
    const { currentYear, currentMonth } = this.getCurrentDateInfo();

    const queryPeriod = strategy.resolvePeriod(period, currentYear, currentMonth);
    const monthDetail = strategy.useMonthDetail();

    this.logger.debug(
      `Strategy ${periodicity}: queryPeriod=${JSON.stringify(queryPeriod)}, monthDetail=${monthDetail}`,
    );

    const cacheKey = this.buildCacheKey('products', {
      flow,
      periodicity,
      period: queryPeriod,
      aggregation,
      topN,
    });

    return this.getCachedValue(cacheKey, async () => {

      const response = await this.queryGeneral({
        flow,
        monthDetail,
        period: queryPeriod,
        filters: [{ filter: 'state', values: [this.CEARA_STATE_ID] }],
        details: [aggregation],
        metrics: ['metricFOB', 'metricKG'],
      });

      const fieldMap: Record<AggregationLevel, { code: string; desc: string }> =
        {
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
        product.percentage =
          totalValue > 0 ? (product.value / totalValue) * 100 : 0;
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
      const [nationalResponse, cearaResponse, statesResponse] =
        await Promise.all([
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

      const nationalTotal = Number(
        nationalResponse.data.list[0]?.metricFOB ?? 0,
      );
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

  async getStatesRanking(
    flow: TradeFlow.EXPORT | TradeFlow.IMPORT,
    period: PeriodDto,
  ): Promise<StateRankingItemDto[]> {
    const cacheKey = this.buildCacheKey('states-ranking', { flow, period });

    return this.getCachedValue(cacheKey, async () => {
      const [
        nationalResponse,
        statesResponse,
        sectorsResponse,
        partnersResponse,
        productsResponse,
      ] = await Promise.all([
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
          details: ['state'],
          metrics: ['metricFOB'],
        }),
        this.queryGeneral({
          flow,
          monthDetail: false,
          period,
          details: ['state', 'ISICSection'],
          metrics: ['metricFOB'],
        }),
        this.queryGeneral({
          flow,
          monthDetail: false,
          period,
          details: ['state', 'country'],
          metrics: ['metricFOB'],
        }),
        this.queryGeneral({
          flow,
          monthDetail: false,
          period,
          details: ['state', 'heading'],
          metrics: ['metricFOB'],
        }),
      ]);

      const nationalTotal = Number(
        nationalResponse.data.list[0]?.metricFOB ?? 0,
      );

      // Aggregate sectors by state
      const sectorsByState = new Map<
        string,
        Array<{ code: string; name: string; value: number }>
      >();
      sectorsResponse.data.list.forEach((item) => {
        const stateName = item.state ?? item.stateName ?? '';
        const sectorCode = String(item.coIsicSection ?? item.ISICSectionCode ?? '');
        const sectorName = item.ISICSection ?? '';
        const value = this.toMillions(item.metricFOB ?? 0);

        if (!stateName || !sectorName) return;

        if (!sectorsByState.has(stateName)) {
          sectorsByState.set(stateName, []);
        }

        sectorsByState.get(stateName)!.push({
          code: sectorCode,
          name: sectorName,
          value,
        });
      });

      // Aggregate partners by state
      const partnersByState = new Map<
        string,
        Array<{ country: string; value: number }>
      >();
      partnersResponse.data.list.forEach((item) => {
        const stateName = item.state ?? item.stateName ?? '';
        const country = item.country ?? item.countryName ?? '';
        const value = this.toMillions(item.metricFOB ?? 0);

        if (!stateName || !country) return;

        if (!partnersByState.has(stateName)) {
          partnersByState.set(stateName, []);
        }

        partnersByState.get(stateName)!.push({ country, value });
      });

      // Aggregate products by state
      const productsByState = new Map<
        string,
        Array<{ code: string; description: string; value: number }>
      >();
      productsResponse.data.list.forEach((item) => {
        const stateName = item.state ?? item.stateName ?? '';
        const code = String(item.headingCode ?? '');
        const description = item.heading ?? '';
        const value = this.toMillions(item.metricFOB ?? 0);

        if (!stateName || !code || !description) return;

        if (!productsByState.has(stateName)) {
          productsByState.set(stateName, []);
        }

        productsByState.get(stateName)!.push({ code, description, value });
      });

      // Build ranking with aggregated data
      return statesResponse.data.list
        .map((item) => ({
          state: item.state ?? item.stateName ?? '',
          value: this.toMillions(item.metricFOB ?? 0),
          rawValue: Number(item.metricFOB ?? 0),
        }))
        .sort((a, b) => b.rawValue - a.rawValue)
        .map((item, index) => {
          const participation =
            nationalTotal > 0 ? (item.rawValue / nationalTotal) * 100 : 0;

          // Get top 5 sectors for this state
          const sectors = sectorsByState.get(item.state) ?? [];
          const sectorTotal = sectors.reduce((sum, s) => sum + s.value, 0);
          const topSectors: StateRankingSectorDto[] = sectors
            .sort((a, b) => b.value - a.value)
            .slice(0, 5)
            .map((s) => ({
              code: s.code,
              name: s.name,
              value: s.value,
              percentage: sectorTotal > 0 ? (s.value / sectorTotal) * 100 : 0,
            }));

          // Get top 5 partners for this state
          const partners = partnersByState.get(item.state) ?? [];
          const partnerTotal = partners.reduce((sum, p) => sum + p.value, 0);
          const topPartners: StateRankingPartnerDto[] = partners
            .sort((a, b) => b.value - a.value)
            .slice(0, 5)
            .map((p) => ({
              country: p.country,
              value: p.value,
              percentage: partnerTotal > 0 ? (p.value / partnerTotal) * 100 : 0,
            }));

          // Get top 5 products for this state
          const products = productsByState.get(item.state) ?? [];
          const productTotal = products.reduce((sum, p) => sum + p.value, 0);
          const topProducts: StateRankingProductDto[] = products
            .sort((a, b) => b.value - a.value)
            .slice(0, 5)
            .map((p) => ({
              code: p.code,
              description: p.description,
              value: p.value,
              percentage: productTotal > 0 ? (p.value / productTotal) * 100 : 0,
            }));

          return {
            rank: index + 1,
            state: item.state,
            value: item.value,
            participation,
            topSectors,
            topPartners,
            topProducts,
          };
        });
    });
  }

  private parseMonth(value: string): { year: number; month: number } {
    const match = /^(\d{4})-(0[1-9]|1[0-2])$/.exec(value);

    if (!match) {
      throw new BadRequestException(
        `Formato de mês inválido: ${value}. Use o padrão YYYY-MM.`,
      );
    }

    return { year: Number(match[1]), month: Number(match[2]) };
  }

  private generateMonthsRange(
    period: PeriodDto,
  ): Array<{ year: number; month: number; key: string }> {
    const start = this.parseMonth(period.from);
    const end = this.parseMonth(period.to);

    if (
      start.year > end.year ||
      (start.year === end.year && start.month > end.month)
    ) {
      throw new BadRequestException(
        'O período inicial deve ser anterior ou igual ao período final.',
      );
    }

    const months: Array<{ year: number; month: number; key: string }> = [];
    let currentYear = start.year;
    let currentMonth = start.month;

    while (
      currentYear < end.year ||
      (currentYear === end.year && currentMonth <= end.month)
    ) {
      const key = `${currentYear}-${String(currentMonth).padStart(2, '0')}`;
      months.push({ year: currentYear, month: currentMonth, key });

      if (currentMonth === 12) {
        currentMonth = 1;
        currentYear += 1;
      } else {
        currentMonth += 1;
      }
    }

    return months;
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
      this.logger.debug('Cache não configurado, executando resolver');
      return resolver();
    }

    const cached = await this.cache.get<T>(key);
    if (cached !== undefined) {
      this.logger.log(`[CACHE HIT] ${this.formatCacheKeyForLog(key)}`);
      return cached;
    }

    this.logger.log(`[CACHE MISS] ${this.formatCacheKeyForLog(key)}`);
    const value = await resolver();
    await this.cache.set(key, value, this.cacheTtlSeconds);
    this.logger.debug(`[CACHE SET] ${this.formatCacheKeyForLog(key)}`);
    return value;
  }

  private formatCacheKeyForLog(key: string): string {
    // Extract the endpoint and parameters from the cache key
    // Format: comexstat:{endpoint}:{json}
    const parts = key.split(':');
    if (parts.length >= 3) {
      const endpoint = parts[1];
      try {
        const params = JSON.parse(parts.slice(2).join(':'));
        return `${endpoint} - ${JSON.stringify(params)}`;
      } catch {
        return key.length > 100 ? key.substring(0, 100) + '...' : key;
      }
    }
    return key.length > 100 ? key.substring(0, 100) + '...' : key;
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
    const reference = new Date(
      Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), 1),
    );
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
    const date = new Date(Date.UTC(2000, month - 1, 15));
    return new Intl.DateTimeFormat('pt-BR', { month: 'short' })
      .format(date)
      .replace('.', '')
      .trim();
  }

  private toMillions(value: unknown): number {
    const numericValue =
      typeof value === 'string'
        ? Number(value.replace(',', '.'))
        : Number(value);

    if (!Number.isFinite(numericValue)) {
      return 0;
    }

    return numericValue / 1_000_000;
  }

  private async queryGeneral(
    params: GeneralQueryParams,
  ): Promise<ComexStatResponse> {
    try {
      const response = await this.http.post<ComexStatResponse>(
        '/general',
        params,
        {
          params: { language: 'pt' },
        },
      );

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
            : (error.response.data?.message ?? 'ComexStat API request failed.');

        throw new HttpException(
          message,
          error.response.status ?? HttpStatus.BAD_GATEWAY,
          {
            cause: error,
          },
        );
      }

      throw new ServiceUnavailableException('Unable to reach ComexStat API.');
    }
  }
}
