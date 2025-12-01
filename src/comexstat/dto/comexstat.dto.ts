import { ApiProperty, ApiPropertyOptional } from '@nestjs/swagger';
import { Transform, Type } from 'class-transformer';
import {
  IsBoolean,
  IsEnum,
  IsIn,
  IsInt,
  IsNotEmpty,
  IsOptional,
  IsPositive,
  IsString,
  ValidateNested,
} from 'class-validator';

const toBoolean = (value: unknown): boolean => {
  if (typeof value === 'boolean') {
    return value;
  }
  if (typeof value === 'string') {
    return value.toLowerCase() === 'true';
  }
  if (typeof value === 'number') {
    return value === 1;
  }
  return false;
};

export enum SummaryPeriod {
  CURRENT_MONTH = 'currentMonth',
  YEAR_TO_DATE = 'yearToDate',
  LAST_YEAR = 'lastYear',
  CUSTOM = 'custom',
}

export enum TradeFlow {
  EXPORT = 'export',
  IMPORT = 'import',
  CURRENT = 'current',
}

export enum TimeSeriesPeriodicity {
  MONTHLY = 'monthly',
  ANNUAL = 'annual',
}

export enum TimeSeriesSeries {
  EXPORT = 'export',
  IMPORT = 'import',
  CURRENT = 'current',
  BALANCE = 'balance',
}

export enum AggregationLevel {
  NCM = 'ncm',
  HEADING = 'heading',
  CHAPTER = 'chapter',
}

export class PeriodDto {
  @ApiProperty({ description: 'Período inicial no formato YYYY-MM.' })
  @IsString()
  @IsNotEmpty()
  from!: string;

  @ApiProperty({ description: 'Período final no formato YYYY-MM.' })
  @IsString()
  @IsNotEmpty()
  to!: string;
}

export class SummaryQueryDto {
  @ApiPropertyOptional({
    enum: SummaryPeriod,
    default: SummaryPeriod.YEAR_TO_DATE,
    description: 'Define o período a ser usado ao montar os dados do resumo.',
  })
  @IsEnum(SummaryPeriod)
  @IsOptional()
  period: SummaryPeriod = SummaryPeriod.YEAR_TO_DATE;

  @ApiPropertyOptional({
    type: PeriodDto,
    description: 'Intervalo personalizado usado quando o período é `custom`.',
  })
  @ValidateNested()
  @Type(() => PeriodDto)
  @IsOptional()
  customPeriod?: PeriodDto;
}

export class SummaryHistoryQueryDto {
  @ApiProperty({ description: 'Período inicial no formato YYYY-MM.' })
  @IsString()
  @IsNotEmpty()
  from!: string;

  @ApiProperty({ description: 'Período final no formato YYYY-MM.' })
  @IsString()
  @IsNotEmpty()
  to!: string;
}

export class TimeSeriesQueryDto {
  @ApiPropertyOptional({
    enum: TimeSeriesPeriodicity,
    default: TimeSeriesPeriodicity.MONTHLY,
  })
  @IsEnum(TimeSeriesPeriodicity)
  @IsOptional()
  periodicity: TimeSeriesPeriodicity = TimeSeriesPeriodicity.MONTHLY;

  @ApiPropertyOptional({
    enum: TimeSeriesSeries,
    default: TimeSeriesSeries.CURRENT,
  })
  @IsEnum(TimeSeriesSeries)
  @IsOptional()
  series: TimeSeriesSeries = TimeSeriesSeries.CURRENT;

  @ApiProperty({
    type: Number,
    description: 'Ano inicial para a consulta da série temporal.',
  })
  @Type(() => Number)
  @IsInt()
  startYear!: number;

  @ApiPropertyOptional({
    type: Number,
    description: 'Ano final opcional para a consulta da série temporal.',
  })
  @Type(() => Number)
  @IsInt()
  @IsOptional()
  endYear?: number;

  @ApiPropertyOptional({
    type: Boolean,
    default: false,
    description: 'Inclui o detalhamento por setor (seções ISIC) na série temporal.',
  })
  @Transform(({ value }) => toBoolean(value))
  @IsBoolean()
  @IsOptional()
  includeSectors = false;
}

export class PartnerCountriesQueryDto {
  @ApiPropertyOptional({
    enum: TradeFlow,
    default: TradeFlow.CURRENT,
    description: 'Fluxo comercial: `export` (Exportações), `import` (Importações) ou `current` (saldo corrente).',
  })
  @IsEnum(TradeFlow)
  @IsOptional()
  flow: TradeFlow = TradeFlow.CURRENT;

  @ApiPropertyOptional({
    enum: SummaryPeriod,
    default: SummaryPeriod.YEAR_TO_DATE,
  })
  @IsEnum(SummaryPeriod)
  @IsOptional()
  period: SummaryPeriod = SummaryPeriod.YEAR_TO_DATE;

  @ApiPropertyOptional({
    type: PeriodDto,
    description: 'Intervalo personalizado usado quando o período é `custom`.',
  })
  @ValidateNested()
  @Type(() => PeriodDto)
  @IsOptional()
  customPeriod?: PeriodDto;

  @ApiPropertyOptional({
    type: Number,
    default: 10,
    description: 'Quantidade de registros que deve ser retornada.',
  })
  @Type(() => Number)
  @IsInt()
  @IsPositive()
  @IsOptional()
  topN = 10;
}

export class TopProductsQueryDto {
  @ApiPropertyOptional({
    enum: TradeFlow,
    default: TradeFlow.EXPORT,
    description: 'Fluxo comercial: `export` (Exportações) ou `import` (Importações).',
  })
  @IsEnum(TradeFlow)
  @IsIn([TradeFlow.EXPORT, TradeFlow.IMPORT])
  @IsOptional()
  flow: TradeFlow.EXPORT | TradeFlow.IMPORT = TradeFlow.EXPORT;

  @ApiPropertyOptional({
    enum: TimeSeriesPeriodicity,
    default: TimeSeriesPeriodicity.ANNUAL,
  })
  @IsEnum(TimeSeriesPeriodicity)
  @IsOptional()
  periodicity: TimeSeriesPeriodicity = TimeSeriesPeriodicity.ANNUAL;

  @ApiPropertyOptional({
    type: Number,
    description: 'Ano a ser utilizado ao consultar dados anuais.',
  })
  @Type(() => Number)
  @IsInt()
  @IsOptional()
  year?: number;

  @ApiPropertyOptional({
    type: PeriodDto,
    description: 'Período personalizado específico para consulta (intervalo YYYY-MM).',
  })
  @ValidateNested()
  @Type(() => PeriodDto)
  @IsOptional()
  period?: PeriodDto;

  @ApiPropertyOptional({
    enum: AggregationLevel,
    default: AggregationLevel.HEADING,
    description: 'Nível de agregação: `ncm` (8 dígitos), `heading` (4 dígitos) ou `chapter` (2 dígitos).',
  })
  @IsEnum(AggregationLevel)
  @IsOptional()
  aggregation: AggregationLevel = AggregationLevel.HEADING;

  @ApiPropertyOptional({
    type: Number,
    default: 20,
  })
  @Type(() => Number)
  @IsInt()
  @IsPositive()
  @IsOptional()
  topN = 20;
}

export class NationalComparisonQueryDto {
  @ApiPropertyOptional({
    enum: TradeFlow,
    default: TradeFlow.EXPORT,
    description: 'Fluxo comercial: `export` (Exportações) ou `import` (Importações).',
  })
  @IsEnum(TradeFlow)
  @IsIn([TradeFlow.EXPORT, TradeFlow.IMPORT])
  @IsOptional()
  flow: TradeFlow.EXPORT | TradeFlow.IMPORT = TradeFlow.EXPORT;

  @ApiProperty({
    description: 'Ponto inicial do intervalo no formato YYYY-MM.',
  })
  @IsString()
  @IsNotEmpty()
  from!: string;

  @ApiProperty({
    description: 'Ponto final do intervalo no formato YYYY-MM.',
  })
  @IsString()
  @IsNotEmpty()
  to!: string;
}

export class DashboardQueryDto {
  @ApiPropertyOptional({
    type: Number,
    description: 'Define qual ano deve ser usado para preencher os dados do painel.',
  })
  @Type(() => Number)
  @IsInt()
  @IsOptional()
  year?: number;
}

const VALUE_DESCRIPTION = 'Valor em milhões de dólares (M USD).';

export class SummaryDataDto {
  @ApiProperty()
  period!: string;

  @ApiProperty({ description: VALUE_DESCRIPTION })
  exports!: number;

  @ApiProperty({ description: VALUE_DESCRIPTION })
  imports!: number;

  @ApiProperty({ description: VALUE_DESCRIPTION })
  tradeBalance!: number;

  @ApiProperty({ description: VALUE_DESCRIPTION })
  tradeCurrent!: number;

  @ApiPropertyOptional()
  exportParticipation?: number;

  @ApiPropertyOptional()
  importParticipation?: number;

  @ApiPropertyOptional()
  exportRanking?: number;

  @ApiPropertyOptional()
  importRanking?: number;
}

export class TimeSeriesSectorDto {
  @ApiProperty()
  code!: string;

  @ApiProperty()
  name!: string;

  @ApiProperty({ description: VALUE_DESCRIPTION })
  value!: number;
}

export class TimeSeriesDataDto {
  @ApiProperty()
  period!: string;

  @ApiPropertyOptional()
  year?: string;

  @ApiPropertyOptional()
  month?: string;

  @ApiPropertyOptional({ description: VALUE_DESCRIPTION })
  exports?: number;

  @ApiPropertyOptional({ description: VALUE_DESCRIPTION })
  imports?: number;

  @ApiPropertyOptional({ description: VALUE_DESCRIPTION })
  balance?: number;

  @ApiPropertyOptional({ description: VALUE_DESCRIPTION })
  current?: number;

  @ApiPropertyOptional({ type: [TimeSeriesSectorDto] })
  sectors?: TimeSeriesSectorDto[];
}

export class PartnerCountryDto {
  @ApiProperty()
  country!: string;

  @ApiPropertyOptional({ description: VALUE_DESCRIPTION })
  exports?: number;

  @ApiPropertyOptional({ description: VALUE_DESCRIPTION })
  imports?: number;

  @ApiPropertyOptional({ description: VALUE_DESCRIPTION })
  current?: number;

  @ApiPropertyOptional({ description: VALUE_DESCRIPTION })
  balance?: number;

  @ApiPropertyOptional()
  percentage?: number;
}

export class ProductDto {
  @ApiProperty()
  code!: string;

  @ApiProperty()
  description!: string;

  @ApiProperty({ description: VALUE_DESCRIPTION })
  value!: number;

  @ApiPropertyOptional()
  quantity?: number;

  @ApiPropertyOptional()
  weight?: number;

  @ApiPropertyOptional()
  percentage?: number;
}

export class NationalComparisonDto {
  @ApiProperty()
  participation!: number;

  @ApiProperty()
  ranking!: number;
}

export class SummaryResponseDto {
  @ApiProperty()
  success!: boolean;

  @ApiProperty({ type: SummaryDataDto })
  data!: SummaryDataDto;
}

export class SummaryHistoryResponseDto {
  @ApiProperty()
  success!: boolean;

  @ApiProperty({ type: [SummaryDataDto] })
  data!: SummaryDataDto[];
}

export class TimeSeriesResponseDto {
  @ApiProperty()
  success!: boolean;

  @ApiProperty({ type: [TimeSeriesDataDto] })
  data!: TimeSeriesDataDto[];
}

export class PartnerCountriesResponseDto {
  @ApiProperty()
  success!: boolean;

  @ApiProperty({ type: [PartnerCountryDto] })
  data!: PartnerCountryDto[];
}

export class TopProductsResponseDto {
  @ApiProperty()
  success!: boolean;

  @ApiProperty({ type: [ProductDto] })
  data!: ProductDto[];
}

export class NationalComparisonResponseDto {
  @ApiProperty()
  success!: boolean;

  @ApiProperty({ type: NationalComparisonDto })
  data!: NationalComparisonDto;
}

export class DashboardDataDto {
  @ApiProperty({ type: SummaryDataDto })
  summary!: SummaryDataDto;

  @ApiProperty({ type: [ProductDto] })
  topExports!: ProductDto[];

  @ApiProperty({ type: [ProductDto] })
  topImports!: ProductDto[];

  @ApiProperty({ type: [PartnerCountryDto] })
  topPartners!: PartnerCountryDto[];
}

export class DashboardResponseDto {
  @ApiProperty()
  success!: boolean;

  @ApiProperty({ type: DashboardDataDto })
  data!: DashboardDataDto;
}
