import { Controller, Delete, Get, Inject, Logger, Query, ValidationPipe } from '@nestjs/common';
import { CACHE_MANAGER } from '@nestjs/cache-manager';
import type { Cache } from 'cache-manager';
import {
  ApiExtraModels,
  ApiOkResponse,
  ApiOperation,
  ApiTags,
} from '@nestjs/swagger';
import {
  AggregationLevel,
  DashboardQueryDto,
  DashboardResponseDto,
  DashboardDataDto,
  NationalComparisonDto,
  NationalComparisonResponseDto,
  NationalComparisonQueryDto,
  StateRankingItemDto,
  StateRankingSectorDto,
  StateRankingPartnerDto,
  StateRankingProductDto,
  StatesRankingResponseDto,
  PartnerCountriesQueryDto,
  PartnerCountriesResponseDto,
  PartnerCountryDto,
  PeriodDto,
  SummaryPeriod,
  SummaryQueryDto,
  SummaryResponseDto,
  SummaryDataDto,
  SummaryHistoryQueryDto,
  SummaryHistoryResponseDto,
  TimeSeriesPeriodicity,
  TimeSeriesQueryDto,
  TimeSeriesSeries,
  TopProductsQueryDto,
  TradeFlow,
  TimeSeriesResponseDto,
  TopProductsResponseDto,
  TimeSeriesDataDto,
  TimeSeriesSectorDto,
} from './dto/comexstat.dto';
import { ComexstatService } from './comexstat.service';

@ApiTags('comexstat')
@ApiExtraModels(
  SummaryResponseDto,
  SummaryHistoryResponseDto,
  SummaryDataDto,
  TimeSeriesResponseDto,
  TimeSeriesDataDto,
  TimeSeriesSectorDto,
  PartnerCountriesResponseDto,
  PartnerCountryDto,
  TopProductsResponseDto,
  DashboardResponseDto,
  DashboardDataDto,
  NationalComparisonResponseDto,
  NationalComparisonDto,
  StatesRankingResponseDto,
  StateRankingItemDto,
  StateRankingSectorDto,
  StateRankingPartnerDto,
  StateRankingProductDto,
)
@Controller('comexstat')
export class ComexstatController {
  private readonly logger = new Logger(ComexstatController.name);

  constructor(
    private readonly comexstatService: ComexstatService,
    @Inject(CACHE_MANAGER) private readonly cacheManager: Cache,
  ) {}

  @Get('summary')
  @ApiOperation({ summary: 'Recupera dados do Quadro Resumo.' })
  @ApiOkResponse({
    description: 'Dados do quadro resumo recuperados com sucesso.',
    type: SummaryResponseDto,
  })
  async getSummary(
    @Query(new ValidationPipe({ transform: true, whitelist: true }))
    query: SummaryQueryDto,
  ): Promise<SummaryResponseDto> {
    // Build customPeriod from periodFrom and periodTo if provided
    let customPeriod: PeriodDto | undefined;

    if (query.periodFrom && query.periodTo) {
      customPeriod = {
        from: query.periodFrom,
        to: query.periodTo,
      };
    }

    const data = await this.comexstatService.getSummaryData(
      query.period ?? SummaryPeriod.YEAR_TO_DATE,
      customPeriod,
    );

    return { success: true, data };
  }

  @Get('summary-history')
  @ApiOperation({
    summary: 'Recupera dados do Quadro Resumo para múltiplos meses.',
  })
  @ApiOkResponse({
    description: 'Dados do quadro resumo por mês recuperados com sucesso.',
    type: SummaryHistoryResponseDto,
  })
  async getSummaryHistory(
    @Query(new ValidationPipe({ transform: true, whitelist: true }))
    query: SummaryHistoryQueryDto,
  ): Promise<SummaryHistoryResponseDto> {
    const data = await this.comexstatService.getSummaryHistory({
      from: query.from,
      to: query.to,
    });

    return { success: true, data };
  }

  @Get('timeseries')
  @ApiOperation({ summary: 'Recupera dados de séries temporais.' })
  @ApiOkResponse({
    description: 'Dados de séries temporais recuperados com sucesso.',
    type: TimeSeriesResponseDto,
  })
  async getTimeSeries(
    @Query(new ValidationPipe({ transform: true, whitelist: true }))
    query: TimeSeriesQueryDto,
  ): Promise<TimeSeriesResponseDto> {
    const data = await this.comexstatService.getTimeSeries(
      query.periodicity ?? TimeSeriesPeriodicity.MONTHLY,
      query.series ?? TimeSeriesSeries.CURRENT,
      query.startYear,
      query.endYear,
      query.includeSectors,
    );

    return { success: true, data };
  }

  @Get('partners')
  @ApiOperation({ summary: 'Recupera informações dos países parceiros.' })
  @ApiOkResponse({
    description: 'Dados de países parceiros recuperados com sucesso.',
    type: PartnerCountriesResponseDto,
  })
  async getPartnerCountries(
    @Query(new ValidationPipe({ transform: true, whitelist: true }))
    query: PartnerCountriesQueryDto,
  ): Promise<PartnerCountriesResponseDto> {
    // Build customPeriod from periodFrom and periodTo if provided
    let customPeriod: PeriodDto | undefined;

    if (query.periodFrom && query.periodTo) {
      customPeriod = {
        from: query.periodFrom,
        to: query.periodTo,
      };
    }

    const data = await this.comexstatService.getPartnerCountries(
      query.flow ?? TradeFlow.CURRENT,
      query.period ?? SummaryPeriod.YEAR_TO_DATE,
      customPeriod,
      query.topN,
    );

    return { success: true, data };
  }

  @Get('products')
  @ApiOperation({ summary: 'Recupera os produtos mais negociados.' })
  @ApiOkResponse({
    description: 'Produtos mais negociados recuperados com sucesso.',
    type: TopProductsResponseDto,
  })
  async getTopProducts(
    @Query(new ValidationPipe({ transform: true, whitelist: true }))
    query: TopProductsQueryDto,
  ): Promise<TopProductsResponseDto> {
    this.logger.debug(
      `Recebido - year: ${query.year}, periodFrom: ${query.periodFrom}, periodTo: ${query.periodTo}`,
    );

    // Build period object from periodFrom and periodTo
    let periodInput: PeriodDto | number | undefined;

    if (query.periodFrom && query.periodTo) {
      periodInput = {
        from: query.periodFrom,
        to: query.periodTo,
      };
      this.logger.debug(`Period construído: ${JSON.stringify(periodInput)}`);
    } else if (query.year !== undefined) {
      periodInput = query.year;
      this.logger.debug(`Usando year: ${periodInput}`);
    } else {
      periodInput = undefined;
      this.logger.debug(`Sem período especificado, usando default`);
    }

    const data = await this.comexstatService.getTopProducts(
      query.flow ?? TradeFlow.EXPORT,
      query.periodicity ?? TimeSeriesPeriodicity.ANNUAL,
      periodInput,
      query.aggregation ?? AggregationLevel.HEADING,
      query.topN,
    );

    return { success: true, data };
  }

  @Get('national-comparison')
  @ApiOperation({ summary: 'Recupera participação nacional e ranking.' })
  @ApiOkResponse({
    description: 'Dados de comparação nacional recuperados com sucesso.',
    type: NationalComparisonResponseDto,
  })
  async getNationalComparison(
    @Query(new ValidationPipe({ transform: true, whitelist: true }))
    query: NationalComparisonQueryDto,
  ): Promise<NationalComparisonResponseDto> {
    const data = await this.comexstatService.getNationalComparison(query.flow, {
      from: query.from,
      to: query.to,
    });

    return { success: true, data };
  }

  @Get('national-comparison/states-ranking')
  @ApiOperation({ summary: 'Recupera ranking de todos os estados ordenado por valor.' })
  @ApiOkResponse({
    description: 'Ranking de estados recuperado com sucesso.',
    type: StatesRankingResponseDto,
  })
  async getStatesRanking(
    @Query(new ValidationPipe({ transform: true, whitelist: true }))
    query: NationalComparisonQueryDto,
  ): Promise<StatesRankingResponseDto> {
    const data = await this.comexstatService.getStatesRanking(query.flow, {
      from: query.from,
      to: query.to,
    });

    return { success: true, data };
  }

  @Get('dashboard')
  @ApiOperation({ summary: 'Recupera dados consolidados do painel.' })
  @ApiOkResponse({
    description: 'Dados do painel recuperados com sucesso.',
    type: DashboardResponseDto,
  })
  async getDashboard(
    @Query(new ValidationPipe({ transform: true, whitelist: true }))
    query: DashboardQueryDto,
  ): Promise<DashboardResponseDto> {
    const targetYear = query.year ?? new Date().getFullYear();

    const [summary, topExports, topImports, topPartners] = await Promise.all([
      this.comexstatService.getSummaryData(SummaryPeriod.YEAR_TO_DATE),
      this.comexstatService.getTopProducts(
        TradeFlow.EXPORT,
        TimeSeriesPeriodicity.ANNUAL,
        targetYear - 1,
        AggregationLevel.HEADING,
        10,
      ),
      this.comexstatService.getTopProducts(
        TradeFlow.IMPORT,
        TimeSeriesPeriodicity.ANNUAL,
        targetYear - 1,
        AggregationLevel.HEADING,
        10,
      ),
      this.comexstatService.getPartnerCountries(
        TradeFlow.CURRENT,
        SummaryPeriod.YEAR_TO_DATE,
        undefined,
        10,
      ),
    ]);

    return {
      success: true,
      data: {
        summary,
        topExports,
        topImports,
        topPartners,
      },
    };
  }

  @Delete('cache')
  @ApiOperation({ summary: 'Limpa o cache de dados do ComexStat (apenas para debug).' })
  async clearCache(): Promise<{ success: boolean; message: string }> {
    // O cache-manager não tem um método reset() global na versão atual
    // Uma alternativa é reiniciar o servidor ou esperar o TTL expirar
    // Para debug, você pode deletar chaves específicas se souber os padrões
    const store = (this.cacheManager as any).store;
    if (store && typeof store.reset === 'function') {
      await store.reset();
      return {
        success: true,
        message: 'Cache limpo com sucesso',
      };
    }
    return {
      success: false,
      message: 'Método reset não disponível. Reinicie o servidor para limpar o cache.',
    };
  }
}
