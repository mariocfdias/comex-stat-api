import { PeriodDto, TimeSeriesPeriodicity } from '../dto/comexstat.dto';

export interface Period {
  from: string;
  to: string;
}

interface PeriodStrategy {
  resolvePeriod(
    period: PeriodDto | number | undefined,
    currentYear: number,
    currentMonth: number,
  ): Period;
  useMonthDetail(): boolean;
}

class MonthlyPeriodStrategy implements PeriodStrategy {
  resolvePeriod(
    period: PeriodDto | number | undefined,
    currentYear: number,
    currentMonth: number,
  ): Period {
    if (period && typeof period === 'object') {
      return { from: period.from, to: period.to };
    }
    const year = typeof period === 'number' ? period : currentYear;
    return {
      from: `${year}-01`,
      to: year === currentYear ? `${year}-${String(currentMonth).padStart(2, '0')}` : `${year}-12`,
    };
  }

  useMonthDetail(): boolean {
    return true;
  }
}

class AnnualPeriodStrategy implements PeriodStrategy {
  resolvePeriod(
    period: PeriodDto | number | undefined,
    currentYear: number,
    _currentMonth: number,
  ): Period {
    if (period && typeof period === 'object') {
      return { from: period.from, to: period.to };
    }
    const year = typeof period === 'number' ? period : currentYear - 1;
    return { from: `${year}-01`, to: `${year}-12` };
  }

  useMonthDetail(): boolean {
    return false;
  }
}

export class PeriodStrategyFactory {
  static create(periodicity: TimeSeriesPeriodicity): PeriodStrategy {
    if (periodicity === TimeSeriesPeriodicity.MONTHLY) {
      return new MonthlyPeriodStrategy();
    }
    return new AnnualPeriodStrategy();
  }
}
