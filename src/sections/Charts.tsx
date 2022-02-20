import * as React from 'react';
import { Box } from '@mui/material';
import CircularProgress from '@mui/material/CircularProgress';
import { LineChart, CartesianGrid, Line, XAxis, YAxis, Tooltip, Legend, ResponsiveContainer } from 'recharts';


interface ChartDataRow {
    date: string;
    value: number;
    investment: number;
    fee: number;
    profit: number;
}

export class Charts extends React.Component<{}, {busy: boolean; data: Array<ChartDataRow>}> {

    constructor(props:{}) {
        super(props);
        this.state = {
            busy: true,
            data: [],
        };
    }

    componentDidMount() {
        fetch('/detail')
            .then<Array<ChartDataRow>>(res => res.json())
            .then(data => this.setState({busy: false, data}));
    }

    render() {

        return <Box>
            <p>TODO Correction for old value + newer investments</p>
            {this.state.busy ?
                <CircularProgress /> :
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