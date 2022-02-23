import { Box, FormControl, InputLabel, Select, MenuItem, ListSubheader } from '@mui/material';
import { LineChart, CartesianGrid, Line, XAxis, YAxis, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { AbstractSection, SectionProps } from '../common';
import { InstrumentDataRow } from './Settings';


interface ChartDataRow {
    date: string;
    value: number;
    investment: number;
    fee: number;
    profit: number;
}

type ChartResponse = Array<ChartDataRow>;

interface ChartState {
    chartData: Array<ChartDataRow>;
    instruments: Array<InstrumentDataRow>;
    types: Array<string>;
    filter: string|null;
}

interface ChartProps {}

export class Charts extends AbstractSection<ChartProps, ChartState> {

    sectionName = () => 'Charts';

    constructor(props: ChartProps & SectionProps) {
        super(props);
        this.state = {
            chartData: [],
            instruments: [],
            types: [],
            filter: null,
        };
    }

    componentDidMount() {
        super.componentDidMount();
        this.props.displayProgressBar(true);
        fetch('/instruments/list')
        .then<Array<InstrumentDataRow>>(res => res.json())
        .then(instruments => {
            fetch('/types/list')
            .then<Array<string>>(res => res.json())
            .then(types => {
                fetch('/charts/get')
                .then<ChartResponse>(res => res.json())
                .then(chartData => {
                    this.setState({chartData, instruments, types});
                    this.props.displayProgressBar(false);
                });
            });
        });
    }

    handleFilterChange(filter: string|null) {
        this.setState({filter});
        this.props.displayProgressBar(true);
        const params = new URLSearchParams();
        if (filter) params.append('filter', filter);
        fetch(`/charts/get?${params.toString()}`)
        .then<ChartResponse>(res => res.json())
        .then(chartData => {
            this.setState({chartData});
            this.props.displayProgressBar(false);
        });
    }

    render() {
        return <Box>
            <FormControl fullWidth size='small'>
                <InputLabel id="filter-select-label">Filter</InputLabel>
                <Select
                    labelId='filter-select-label'
                    value={this.state.filter}
                    label="Filter"
                    onChange={(e) => this.handleFilterChange(e.target.value)}
                >
                    <MenuItem>---</MenuItem>
                    <ListSubheader>types</ListSubheader>
                    {this.state.types.map(v => <MenuItem value={v}>{v}</MenuItem>)}
                    <ListSubheader>instruments</ListSubheader>
                    {this.state.instruments.map(v => <MenuItem value={v.ticker}>{v.ticker}</MenuItem>)}
                </Select>
            </FormControl>

            {this.state.chartData.length > 0 ?
                <ResponsiveContainer width="100%" height={600}>
                    <LineChart data={this.state.chartData} margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
                        <CartesianGrid strokeDasharray="3 3" />
                        <Line type="monotone" dataKey="value" dot={false} stroke="#8884d8" />
                        <Line type="monotone" dataKey="investment" dot={false} stroke="#82ca9d" />
                        <Line type="monotone" dataKey="profit" dot={false} stroke="#ff704d" />
                        <XAxis dataKey="date" angle={30} dy={30} dx={6} height={80}/>
                        <YAxis tickFormatter={(v, i) => this.formatCurrency(v)||''} width={100}/>
                        <Tooltip />
                        <Legend />
                    </LineChart>
                </ResponsiveContainer> :
                null
            }
        </Box>
    }
}