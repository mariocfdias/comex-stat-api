import { PeriodDto } from '../dto/comexstat.dto';

export interface Period {
  from: string;
  to: string;
}

export interface PeriodStrategy {
  /**
   * Resolve the period based on the input (year, period, or undefined)
   */
  resolvePeriod(
    input: PeriodDto | number | undefined,
    currentYear: number,
    currentMonth: number,
  ): Period;

  /**
   * Determines if month detail should be used in the API query
   */
  useMonthDetail(): boolean;
}

/**
 * Strategy for annual periodicity
 * - Accepts a year (number) or undefined (uses previous year)
 * - Always returns full year (January to December)
 * - Does not use month detail
 */
export class AnnualPeriodStrategy implements PeriodStrategy {
  resolvePeriod(
    input: PeriodDto | number | undefined,
    currentYear: number,
  ): Period {
    const year =
      typeof input === 'number' ? input : input ? undefined : currentYear - 1;

    if (year === undefined) {
      throw new Error(
        'For annual periodicity, provide a year number or leave empty to use previous year',
      );
    }

    return {
      from: this.formatPeriod(year, 1),
      to: this.formatPeriod(year, 12),
    };
  }

  useMonthDetail(): boolean {
    return false;
  }

  private formatPeriod(year: number, month: number): string {
    const paddedMonth = String(month).padStart(2, '0');
    return `${year}-${paddedMonth}`;
  }
}

/**
 * Strategy for monthly periodicity
 * - Requires a PeriodDto (from/to) or uses year-to-date if undefined
 * - Returns the exact period specified
 * - Uses month detail
 */
export class MonthlyPeriodStrategy implements PeriodStrategy {
  resolvePeriod(
    input: PeriodDto | number | undefined,
    currentYear: number,
    currentMonth: number,
  ): Period {
    // If input is a PeriodDto, use it directly
    if (input && typeof input === 'object' && 'from' in input && 'to' in input) {
      return input;
    }

    // If input is a year number, return the full year (for backward compatibility)
    if (typeof input === 'number') {
      return {
        from: this.formatPeriod(input, 1),
        to: this.formatPeriod(input, 12),
      };
    }

    // If undefined, use year-to-date
    return {
      from: this.formatPeriod(currentYear, 1),
      to: this.formatPeriod(currentYear, currentMonth),
    };
  }

  useMonthDetail(): boolean {
    return true;
  }

  private formatPeriod(year: number, month: number): string {
    const paddedMonth = String(month).padStart(2, '0');
    return `${year}-${paddedMonth}`;
  }
}

/**
 * Factory to create the appropriate strategy based on periodicity
 */
export class PeriodStrategyFactory {
  static create(periodicity: 'monthly' | 'annual'): PeriodStrategy {
    switch (periodicity) {
      case 'monthly':
        return new MonthlyPeriodStrategy();
      case 'annual':
        return new AnnualPeriodStrategy();
      default:
        throw new Error(`Unknown periodicity: ${periodicity}`);
    }
  }
}
