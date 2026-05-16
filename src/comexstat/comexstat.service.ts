import {
  BadRequestException,
  Inject,
  Injectable,
  Logger,
} from '@nestjs/common';
import { CACHE_MANAGER } from '@nestjs/cache-manager';
import { InjectRepository } from '@nestjs/typeorm';
import { Repository } from 'typeorm';
import type { Cache } from 'cache-manager';
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
import { ComexstatSummary } from './entities/comexstat-summary.entity';
import { ComexstatSummaryHistory } from './entities/comexstat-summary-history.entity';
import { ComexstatTimeseries } from './entities/comexstat-timeseries.entity';
import { ComexstatPartner } from './entities/comexstat-partner.entity';
import { ComexstatProduct } from './entities/comexstat-product.entity';
import { ComexstatNational } from './entities/comexstat-national.entity';
import { ComexstatStatesRanking } from './entities/comexstat-states-ranking.entity';

@Injectable()
export class ComexstatService {
  private readonly logger = new Logger(ComexstatService.name);
  private readonly cacheNamespace = 'comexstat';
  private readonly cacheTtlSeconds = 60 * 60 * 24;

  constructor(
    @Inject(CACHE_MANAGER) private readonly cache: Cache,
    @InjectRepository(ComexstatSummary)
    private readonly summaryRepo: Repository<ComexstatSummary>,
    @InjectRepository(ComexstatSummaryHistory)
    private readonly summaryHistoryRepo: Repository<ComexstatSummaryHistory>,
    @InjectRepository(ComexstatTimeseries)
    private readonly timeseriesRepo: Repository<ComexstatTimeseries>,
    @InjectRepository(ComexstatPartner)
    private readonly partnerRepo: Repository<ComexstatPartner>,
    @InjectRepository(ComexstatProduct)
    private readonly productRepo: Repository<ComexstatProduct>,
    @InjectRepository(ComexstatNational)
    private readonly nationalRepo: Repository<ComexstatNational>,
    @InjectRepository(ComexstatStatesRanking)
    private readonly statesRankingRepo: Repository<ComexstatStatesRanking>,
  ) {}

  async getSummaryData(
    periodType: SummaryPeriod,
    customPeriod?: PeriodDto,
  ): Promise<SummaryDataDto> {
    const cacheKey = this.buildCacheKey('summary', { periodType, customPeriod });
    return this.getCachedValue(cacheKey, async () => {
      const row = await this.summaryRepo.findOne({ where: { periodType } });
      if (!row) {
        return { period: periodType, exports: 0, imports: 0, tradeBalance: 0, tradeCurrent: 0 };
      }
      const exp = Number(row.exportFob ?? 0);
      const imp = Number(row.importFob ?? 0);
      return {
        period: row.periodLabel,
        exports: exp,
        imports: imp,
        tradeBalance: Number(row.balance ?? 0),
        tradeCurrent: exp + imp,
      };
    });
  }

  async getSummaryHistory(period: PeriodDto): Promise<SummaryDataDto[]> {
    const cacheKey = this.buildCacheKey('summary-history', period);
    return this.getCachedValue(cacheKey, async () => {
      const [fromYear, fromMonth] = period.from.split('-').map(Number);
      const [toYear, toMonth] = period.to.split('-').map(Number);

      const rows = await this.summaryHistoryRepo
        .createQueryBuilder('h')
        .where('(h.year > :fromYear OR (h.year = :fromYear AND h.month >= :fromMonth))', { fromYear, fromMonth })
        .andWhere('(h.year < :toYear OR (h.year = :toYear AND h.month <= :toMonth))', { toYear, toMonth })
        .orderBy('h.year', 'ASC').addOrderBy('h.month', 'ASC')
        .getMany();

      return rows.map((r) => ({
        period: `${r.year}-${String(r.month).padStart(2, '0')}`,
        exports: Number(r.exportFob ?? 0),
        imports: Number(r.importFob ?? 0),
        tradeBalance: Number(r.balance ?? 0),
        tradeCurrent: Number(r.exportFob ?? 0) + Number(r.importFob ?? 0),
      }));
    });
  }

  async getTimeSeries(
    periodicity: TimeSeriesPeriodicity,
    series: TimeSeriesSeries,
    startYear: number,
    endYear?: number,
    _includeSectors?: boolean,
  ): Promise<TimeSeriesDataDto[]> {
    const cacheKey = this.buildCacheKey('timeseries', { periodicity, series, startYear, endYear });
    return this.getCachedValue(cacheKey, async () => {
      const effectiveEnd = endYear ?? new Date().getFullYear();
      const seriesValues =
        series === TimeSeriesSeries.CURRENT || series === TimeSeriesSeries.BALANCE
          ? ['export', 'import']
          : [series as string];

      const rows = await this.timeseriesRepo
        .createQueryBuilder('t')
        .where('t.periodicity = :periodicity', { periodicity })
        .andWhere('t.series IN (:...seriesValues)', { seriesValues })
        .andWhere('t.year >= :startYear AND t.year <= :endYear', { startYear, endYear: effectiveEnd })
        .orderBy('t.year', 'ASC').addOrderBy('t.month', 'ASC')
        .getMany();

      const byPeriod = new Map<string, TimeSeriesDataDto>();
      for (const row of rows) {
        const key = periodicity === TimeSeriesPeriodicity.MONTHLY
          ? `${row.year}-${String(row.month).padStart(2, '0')}`
          : String(row.year);
        if (!byPeriod.has(key)) byPeriod.set(key, { period: key, year: String(row.year) });
        const entry = byPeriod.get(key)!;
        if (row.series === 'export') entry.exports = Number(row.value ?? 0);
        if (row.series === 'import') entry.imports = Number(row.value ?? 0);
      }

      return Array.from(byPeriod.values()).map((e) => ({
        ...e,
        balance: (e.exports ?? 0) - (e.imports ?? 0),
        current: (e.exports ?? 0) + (e.imports ?? 0),
      }));
    });
  }

  async getPartnerCountries(
    flow: TradeFlow,
    periodType: SummaryPeriod,
    customPeriod?: PeriodDto,
    topN = 10,
  ): Promise<PartnerCountryDto[]> {
    const cacheKey = this.buildCacheKey('partners', { flow, periodType, customPeriod, topN });
    return this.getCachedValue(cacheKey, async () => {
      const { from, to } = this.resolvePeriod(periodType, customPeriod);
      const flows = flow === TradeFlow.CURRENT
        ? ['export', 'import']
        : [flow as string];

      const rows = await this.partnerRepo
        .createQueryBuilder('p')
        .where('p.flow IN (:...flows)', { flows })
        .andWhere('p.periodFrom = :from AND p.periodTo = :to', { from, to })
        .orderBy('p.fobValue', 'DESC')
        .getMany();

      const byCountry = new Map<string, PartnerCountryDto>();
      for (const r of rows) {
        const name = r.countryName ?? r.countryCode;
        if (!byCountry.has(name)) byCountry.set(name, { country: name });
        const entry = byCountry.get(name)!;
        if (r.flow === 'export') entry.exports = Number(r.fobValue ?? 0);
        if (r.flow === 'import') entry.imports = Number(r.fobValue ?? 0);
      }

      return Array.from(byCountry.values())
        .map((e) => ({ ...e, current: (e.exports ?? 0) + (e.imports ?? 0), balance: (e.exports ?? 0) - (e.imports ?? 0) }))
        .sort((a, b) => (b.current ?? 0) - (a.current ?? 0))
        .slice(0, topN);
    });
  }

  async getTopProducts(
    flow: TradeFlow.EXPORT | TradeFlow.IMPORT,
    periodicity: TimeSeriesPeriodicity,
    period: PeriodDto | number | undefined,
    aggregation: AggregationLevel,
    topN = 20,
  ): Promise<ProductDto[]> {
    const cacheKey = this.buildCacheKey('products', { flow, periodicity, period, aggregation, topN });
    return this.getCachedValue(cacheKey, async () => {
      const { from, to } = this.resolvePeriodFromInput(period, periodicity);

      const rows = await this.productRepo
        .createQueryBuilder('p')
        .where('p.flow = :flow', { flow })
        .andWhere('p.periodicity = :periodicity', { periodicity })
        .andWhere('p.periodFrom = :from AND p.periodTo = :to', { from, to })
        .andWhere('p.aggregation = :aggregation', { aggregation })
        .orderBy('p.fobValue', 'DESC')
        .limit(topN)
        .getMany();

      return rows.map((r) => ({
        code: r.code,
        description: r.description ?? '',
        value: Number(r.fobValue ?? 0),
        weight: r.weightKg ? Number(r.weightKg) : undefined,
        percentage: r.share ? Number(r.share) * 100 : undefined,
      }));
    });
  }

  async getNationalComparison(
    flow: TradeFlow.EXPORT | TradeFlow.IMPORT,
    period: PeriodDto,
  ): Promise<NationalComparisonDto> {
    const cacheKey = this.buildCacheKey('national-comparison', { flow, period });
    return this.getCachedValue(cacheKey, async () => {
      const row = await this.nationalRepo.findOne({
        where: { flow, periodFrom: period.from, periodTo: period.to },
      });
      if (!row) return { participation: 0, ranking: 0 };
      return {
        participation: Number(row.cearaShare ?? 0) * 100,
        ranking: row.cearaRank ?? 0,
      };
    });
  }

  async getStatesRanking(
    flow: TradeFlow.EXPORT | TradeFlow.IMPORT,
    period: PeriodDto,
  ): Promise<StateRankingItemDto[]> {
    const cacheKey = this.buildCacheKey('states-ranking', { flow, period });
    return this.getCachedValue(cacheKey, async () => {
      const rows = await this.statesRankingRepo.find({
        where: { flow, periodFrom: period.from, periodTo: period.to },
        order: { ranking: 'ASC' },
      });

      return rows.map((r) => ({
        rank: r.ranking ?? 0,
        state: r.stateName ?? r.stateCode,
        value: Number(r.fobValue ?? 0),
        participation: Number(r.share ?? 0) * 100,
        topSectors: (r.sectors as StateRankingSectorDto[]) ?? [],
        topPartners: (r.topPartners as StateRankingPartnerDto[]) ?? [],
        topProducts: (r.topProducts as StateRankingProductDto[]) ?? [],
      }));
    });
  }

  // ── Helpers ──────────────────────────────────────────────────────────────────

  private resolvePeriod(periodType: SummaryPeriod, customPeriod?: PeriodDto): { from: string; to: string } {
    const now = new Date();
    const year = now.getFullYear();
    const month = now.getMonth() + 1;
    const fmt = (y: number, m: number) => `${y}-${String(m).padStart(2, '0')}`;

    switch (periodType) {
      case SummaryPeriod.CURRENT_MONTH: {
        const prevMonth = month === 1 ? 12 : month - 1;
        const prevYear = month === 1 ? year - 1 : year;
        return { from: fmt(prevYear, prevMonth), to: fmt(prevYear, prevMonth) };
      }
      case SummaryPeriod.YEAR_TO_DATE:
        return { from: fmt(year, 1), to: fmt(year, month) };
      case SummaryPeriod.LAST_YEAR:
        return { from: fmt(year - 1, 1), to: fmt(year - 1, 12) };
      case SummaryPeriod.CUSTOM:
        if (!customPeriod) throw new BadRequestException('customPeriod required for period=custom');
        return { from: customPeriod.from, to: customPeriod.to };
    }
  }

  private resolvePeriodFromInput(
    period: PeriodDto | number | undefined,
    periodicity: TimeSeriesPeriodicity,
  ): { from: string; to: string } {
    if (period && typeof period === 'object') {
      return { from: period.from, to: period.to };
    }
    const year = typeof period === 'number' ? period : new Date().getFullYear() - 1;
    return { from: `${year}-01`, to: `${year}-12` };
  }

  private buildCacheKey(segment: string, payload: unknown): string {
    return `${this.cacheNamespace}:${segment}:${this.serializeForCache(payload)}`;
  }

  private serializeForCache(value: unknown): string {
    const normalize = (input: unknown): unknown => {
      if (Array.isArray(input)) return input.map(normalize);
      if (input && typeof input === 'object') {
        return Object.keys(input as Record<string, unknown>)
          .sort()
          .reduce((acc, key) => {
            const v = normalize((input as Record<string, unknown>)[key]);
            if (v !== undefined) acc[key] = v;
            return acc;
          }, {} as Record<string, unknown>);
      }
      return input;
    };
    return JSON.stringify(normalize(value));
  }

  private async getCachedValue<T>(key: string, resolver: () => Promise<T>): Promise<T> {
    if (!this.cache) return resolver();
    const cached = await this.cache.get<T>(key);
    if (cached !== undefined) return cached;
    const value = await resolver();
    await this.cache.set(key, value, this.cacheTtlSeconds);
    return value;
  }
}
