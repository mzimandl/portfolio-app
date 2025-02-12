import { Box, FormControl, InputLabel, Select, MenuItem, Slider } from '@mui/material';
import { CartesianGrid, XAxis, YAxis, Tooltip, Area, ResponsiveContainer, ComposedChart, Bar, Cell, Line, Scatter } from 'recharts';
import { AbstractSection, SectionProps } from '../common';
import { InstrumentDataRow } from './Settings';


interface ChartDataRow {
    date: string;
    open: number;
    close: number;
    high: number;
    low: number;
    dividends: number;
    splits: number;
}

type ChartResponse = Array<ChartDataRow>;

interface PricesState {
    chartData: Array<ChartDataRow>;
    instruments: Array<InstrumentDataRow>;
    filter: string|null;
    currency?: string;
    dateRange: number[];
}

interface PricesProps {}

export class Prices extends AbstractSection<PricesProps, PricesState> {

    sectionName = () => 'Prices';

    constructor(props: PricesProps & SectionProps) {
        super(props);
        this.state = {
            chartData: [],
            instruments: [],
            filter: null,
            currency: undefined,
            dateRange: [0, 0],
        };
    }

    componentDidMount() {
        super.componentDidMount();
        this.props.displayProgressBar(true);
        fetch('/instruments/list')
        .then<Array<InstrumentDataRow>>(res => res.json())
        .then(instruments => {
            this.setState({instruments: instruments.filter(v => v.evaluation !== 'manual')});
            this.props.displayProgressBar(false);
        });
    }

    handleFilterChange(filter: string|null) {
        const currency = this.state.instruments.find(v => v.ticker === filter)?.currency;
        this.setState({filter, currency});
        this.props.displayProgressBar(true);
        const params = new URLSearchParams();
        if (filter) params.append('filter', filter);
        fetch(`/prices/get?${params.toString()}`)
        .then<ChartResponse>(res => res.json())
        .then(chartData => {
            this.setState({chartData, dateRange: [0, chartData.length]});
            this.props.displayProgressBar(false);
        });
    }

    render() {
        const onlyClose = this.state.chartData.every(item => !item.open && !item.high && !item.low);

        return <Box>
            <FormControl fullWidth size='small'>
                <InputLabel id="filter-select-label">Filter</InputLabel>
                <Select
                    labelId='filter-select-label'
                    value={this.state.filter}
                    label="Filter"
                    onChange={(e) => this.handleFilterChange(e.target.value)}
                >
                    {this.state.instruments.map(v => <MenuItem value={v.ticker}>{v.ticker}</MenuItem>)}
                </Select>
            </FormControl>

            <Slider
                getAriaLabel={() => 'Date range'}
                value={this.state.dateRange}
                onChange={(event, dateRange) => { if (Array.isArray(dateRange)) this.setState({dateRange})}}
                valueLabelDisplay="auto"
                min={0} max={this.state.chartData.length}
            />

            {this.state.chartData.length > 0 ?
                <ResponsiveContainer width="100%" height={600}>
                    <ComposedChart data={this.state.chartData.slice(this.state.dateRange[0], this.state.dateRange[1])} margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
                        <CartesianGrid strokeDasharray="3 3" />
                        {onlyClose ?
                            <Line dataKey="close" stroke="#8884d8" dot={false} /> :
                            [
                                <Area dataKey={obj => [obj['low'], obj['high']]} stroke="#8884d8" opacity={0.4} name="Low/high"/>,
                                <Bar dataKey={obj => [obj['open'], obj['close']]} name="Open/close" >
                                    {this.state.chartData.map((item, index) =>
                                        <Cell key={`cell-${index}`} fill={item['close'] >= item['open'] ? '#56DD00' : '#FF3737'} />
                                    )}
                                </Bar>,
                            ]
                        }
                        <Scatter name="Dividends" dataKey={obj => obj['dividends'] > 0 ? obj['dividends'] : null} shape="diamond" fill="#8884d8" />
                        <Scatter name="Splits" dataKey={obj => obj['splits'] > 0 ? obj['splits'] : null} shape="wye" fill="#8884d8" />
                        <XAxis dataKey="date" angle={30} dy={30} dx={6} height={80}/>
                        <YAxis tickFormatter={(v, i) => this.formatCurrency(v, {currency: this.state.currency})||''} width={100}/>
                        <Tooltip formatter={(value: number) => this.formatCurrency(value, {currency: this.state.currency})} />
                    </ComposedChart>
                </ResponsiveContainer> :
                null
            }
        </Box>
    }
}