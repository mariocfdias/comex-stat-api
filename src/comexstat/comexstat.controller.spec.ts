import { Test, TestingModule } from '@nestjs/testing';
import { ComexstatController } from './comexstat.controller';
import { ComexstatService } from './comexstat.service';

describe('ComexstatController', () => {
  let controller: ComexstatController;
  let service: jest.Mocked<ComexstatService>;

  beforeEach(async () => {
    const module: TestingModule = await Test.createTestingModule({
      controllers: [ComexstatController],
      providers: [
        {
          provide: ComexstatService,
          useValue: {
            getSummaryData: jest.fn(),
            getSummaryHistory: jest.fn(),
            getTimeSeries: jest.fn(),
            getPartnerCountries: jest.fn(),
            getTopProducts: jest.fn(),
            getNationalComparison: jest.fn(),
          },
        },
      ],
    }).compile();

    service = module.get(ComexstatService);
    controller = module.get<ComexstatController>(ComexstatController);
  });

  it('should be defined', () => {
    expect(controller).toBeDefined();
  });

  it('should return summary history payload', async () => {
    const summaryHistory = [
      { period: 'jan/2024', exports: 1, imports: 2, tradeBalance: -1, tradeCurrent: 3 },
    ];
    service.getSummaryHistory.mockResolvedValue(summaryHistory as any);

    const response = await controller.getSummaryHistory({ from: '2024-01', to: '2024-02' } as any);

    expect(service.getSummaryHistory).toHaveBeenCalledWith({ from: '2024-01', to: '2024-02' });
    expect(response).toEqual({ success: true, data: summaryHistory });
  });
});
