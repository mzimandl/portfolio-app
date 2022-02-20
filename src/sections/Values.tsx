import * as React from 'react';
import { Table, TableBody, TableHead, TableContainer, TableRow, TableCell, Box, IconButton, FormControl, Select, InputLabel, MenuItem } from '@mui/material';
import CircularProgress from '@mui/material/CircularProgress';
import TextField from '@mui/material/TextField';
import { AddBox } from '@mui/icons-material';
import { InstrumentDataRow } from './Settings';


interface DataRow {
    date: string;
    ticker: string;
    value: number;
}

interface NewDataRow {
    date: string;
    ticker: string;
    value: string;
}

export class Values extends React.Component<{}, {busy: boolean; values: Array<DataRow>; newValue: NewDataRow; instruments: Array<InstrumentDataRow>}> {

    constructor(props:{}) {
        super(props);
        this.state = {
            busy: true,
            values: [],
            instruments: [],
            newValue: {
                date: '',
                ticker: '',
                value: '',
            }
        };

        this.loadInstruments = this.loadInstruments.bind(this);
        this.loadValues = this.loadValues.bind(this);

        this.addValue = this.addValue.bind(this);
    }

    componentDidMount() {
        this.loadInstruments().then(() =>
            this.loadValues().then(() =>
                this.setState({busy: false})
            )
        );
    }

    loadInstruments = () => {
        return fetch('/instruments/list')
            .then(res => res.json())
            .then(instruments => this.setState({instruments}));
    }

    loadValues = () => {
        const params = new URLSearchParams();
        // params.append('ticker', 'CEZ.PR');
        return fetch(`/values/list?${params.toString()}`)
            .then(res => res.json())
            .then(values => this.setState({values}));
    }

    addValue = () => {
        if (this.state.newValue.ticker && this.state.newValue.date && this.state.newValue.value) {
            this.setState({busy: true});
            fetch('/values/new', {method: 'POST', body: JSON.stringify(this.state.newValue)})
                .then(res => {
                    this.setState({
                        newValue: {
                            date: '',
                            ticker: '',
                            value: '',
                        }
                    });
                    this.loadValues().then(() => this.setState({busy: false}));
                });
        }
    }

    render() {

        return <Box>
            {this.state.busy ?
                <CircularProgress /> :
                <TableContainer>
                    <Table size="small">
                        <TableHead>
                            <TableRow>
                                <TableCell>
                                    <TextField label="Date" variant="outlined" size='small' margin='none' fullWidth
                                    onChange={(e) => this.setState({newValue: {...this.state.newValue, date: e.target.value}})} />
                                </TableCell>
                                <TableCell>
                                    <FormControl fullWidth size='small'>
                                        <InputLabel id="ticker-select-label">Ticker</InputLabel>
                                        <Select
                                            labelId='ticker-select-label'
                                            value={this.state.newValue.ticker}
                                            label="Ticker"
                                            onChange={(e) => this.setState({newValue: {...this.state.newValue, ticker: e.target.value}})}
                                        >
                                            {this.state.instruments.map(v => <MenuItem key={v.ticker} value={v.ticker}>{v.ticker}</MenuItem>)}
                                        </Select>
                                    </FormControl>
                                </TableCell>
                                <TableCell>
                                    <TextField label="Value" variant="outlined" size='small' margin='none' fullWidth
                                    onChange={(e) => this.setState({newValue: {...this.state.newValue, value: e.target.value}})} />
                                </TableCell>
                                <TableCell><IconButton onClick={this.addValue}><AddBox/></IconButton></TableCell>
                            </TableRow>
                        </TableHead>
                        <TableBody>
                            {this.state.values.map(
                                (item, i) => <TableRow key={i}>
                                    <TableCell>{item.date}</TableCell>
                                    <TableCell>{item.ticker}</TableCell>
                                    <TableCell>{item.value}</TableCell>
                                    <TableCell></TableCell>
                                </TableRow>
                            )}
                        </TableBody>
                    </Table>
                </TableContainer>}
        </Box>
    }
}