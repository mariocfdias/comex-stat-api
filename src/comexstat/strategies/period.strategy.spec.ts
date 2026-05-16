import {
  AnnualPeriodStrategy,
  MonthlyPeriodStrategy,
  PeriodStrategyFactory,
} from './period.strategy';

describe('PeriodStrategy', () => {
  describe('AnnualPeriodStrategy', () => {
    const strategy = new AnnualPeriodStrategy();

    it('should use month detail = false', () => {
      expect(strategy.useMonthDetail()).toBe(false);
    });

    it('should expand a year number to full year period', () => {
      const period = strategy.resolvePeriod(2020, 2024, 6);

      expect(period).toEqual({
        from: '2020-01',
        to: '2020-12',
      });
    });

    it('should use previous year when input is undefined', () => {
      const period = strategy.resolvePeriod(undefined, 2024, 6);

      expect(period).toEqual({
        from: '2023-01',
        to: '2023-12',
      });
    });

    it('should throw error when input is a PeriodDto (not supported for annual)', () => {
      expect(() => {
        strategy.resolvePeriod({ from: '2020-01', to: '2020-06' }, 2024, 6);
      }).toThrow();
    });
  });

  describe('MonthlyPeriodStrategy', () => {
    const strategy = new MonthlyPeriodStrategy();

    it('should use month detail = true', () => {
      expect(strategy.useMonthDetail()).toBe(true);
    });

    it('should use PeriodDto directly when provided', () => {
      const period = strategy.resolvePeriod(
        { from: '2020-03', to: '2020-07' },
        2024,
        6,
      );

      expect(period).toEqual({
        from: '2020-03',
        to: '2020-07',
      });
    });

    it('should expand year to full year for backward compatibility', () => {
      const period = strategy.resolvePeriod(2020, 2024, 6);

      expect(period).toEqual({
        from: '2020-01',
        to: '2020-12',
      });
    });

    it('should use year-to-date when input is undefined', () => {
      const period = strategy.resolvePeriod(undefined, 2024, 6);

      expect(period).toEqual({
        from: '2024-01',
        to: '2024-06',
      });
    });
  });

  describe('PeriodStrategyFactory', () => {
    it('should create AnnualPeriodStrategy for annual periodicity', () => {
      const strategy = PeriodStrategyFactory.create('annual');
      expect(strategy).toBeInstanceOf(AnnualPeriodStrategy);
    });

    it('should create MonthlyPeriodStrategy for monthly periodicity', () => {
      const strategy = PeriodStrategyFactory.create('monthly');
      expect(strategy).toBeInstanceOf(MonthlyPeriodStrategy);
    });

    it('should throw error for unknown periodicity', () => {
      expect(() => {
        PeriodStrategyFactory.create('unknown' as any);
      }).toThrow('Unknown periodicity: unknown');
    });
  });
});
