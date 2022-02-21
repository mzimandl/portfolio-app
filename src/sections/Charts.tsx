import { Box } from '@mui/material';
import { LineChart, CartesianGrid, Line, XAxis, YAxis, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { AbstractSection, SectionProps } from './common';


interface ChartDataRow {
    date: string;
    value: number;
    investment: number;
    fee: number;
    profit: number;
}

interface ChartState {
    isBusy: boolean;
    data: Array<ChartDataRow>;
}

interface ChartProps {}

export class Charts extends AbstractSection<ChartProps, ChartState> {

    sectionName = () => 'Charts';

    constructor(props: ChartProps & SectionProps) {
        super(props);
        this.state = {
            isBusy: false,
            data: [],
        };
    }

    componentDidMount() {
        super.componentDidMount();
        this.setState({isBusy: true});
        this.props.displayProgressBar(true);
        fetch('/detail')
            .then<Array<ChartDataRow>>(res => res.json())
            .then(data => {
                this.setState({isBusy: false, data});
                this.props.displayProgressBar(false);
            });
    }

    render() {

        return <Box>
            <p>TODO Correction for old value + newer investments</p>
            {this.state.isBusy ?
                null :
                <ResponsiveContainer width="100%" height={500}>
                    <LineChart data={this.state.data} margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
                        <CartesianGrid strokeDasharray="3 3" />
                        <Line type="monotone" dataKey="value" dot={false} stroke="#8884d8" />
                        <Line type="monotone" dataKey="investment" dot={false} stroke="#82ca9d" />
                        <Line type="monotone" dataKey="profit" dot={false} stroke="#ff704d" />
                        <XAxis dataKey="date" />
                        <YAxis />
                        <Tooltip />
                        <Legend />
                    </LineChart>
                </ResponsiveContainer>
            }
        </Box>
    }
}