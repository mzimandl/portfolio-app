import React from 'react';
import { AbstractSection, SectionProps } from '../../common';
import { Table, TableBody, TableHead, TableContainer, TableRow, TableCell, Box, IconButton, FormControl, Select, InputLabel, MenuItem } from '@mui/material';
import TextField from '@mui/material/TextField';
import { AddBox } from '@mui/icons-material';
import { InstrumentDataRow } from '../Settings';


interface DataRow {
    date: string;
    ticker: string;
    value: number;
    currency: string;
}

interface NewDataRow {
    date: string;
    ticker: string;
    value: string;
}

type ValuesResponse = Array<DataRow>;

interface ValuesState {
    values: Array<DataRow>;
    instruments: Array<InstrumentDataRow>;
}

interface ValuesProps {}
interface NewValueProps {
    instruments:Array<InstrumentDataRow>;
    addValue:(newValue: NewDataRow) => void;
}

class NewValueTableRow extends React.Component<NewValueProps, NewDataRow> {

    constructor(props: NewValueProps) {
        super(props);
        this.state = {
            date: '',
            ticker: '',
            value: '',
        };
    }

    render() {
        return <TableRow>
            <TableCell>
                <TextField label="Date" variant="outlined" size='small' margin='none' fullWidth
                onChange={(e) => this.setState({date: e.target.value})} />
            </TableCell>
            <TableCell>
                <FormControl fullWidth size='small'>
                    <InputLabel id="ticker-select-label">Ticker</InputLabel>
                    <Select
                        labelId='ticker-select-label'
                        value={this.state.ticker}
                        label="Ticker"
                        onChange={(e) => this.setState({ticker: e.target.value})}
                    >
                        {this.props.instruments
                            .filter(v => v.evaluation === 'manual')
                            .map(v => <MenuItem key={v.ticker} value={v.ticker}>{v.ticker}</MenuItem>)
                        }
                    </Select>
                </FormControl>
            </TableCell>
            <TableCell>
                <TextField label="Value" variant="outlined" size='small' margin='none' fullWidth
                onChange={(e) => this.setState({value: e.target.value})} />
            </TableCell>
            <TableCell><IconButton onClick={e => this.props.addValue(this.state)}><AddBox/></IconButton></TableCell>
        </TableRow>
    }
}

export class Values extends AbstractSection<ValuesProps, ValuesState> {

    sectionName = () => 'Values';

    constructor(props: ValuesProps & SectionProps) {
        super(props);
        this.state = {
            values: [],
            instruments: [],
        };

        this.addValue = this.addValue.bind(this);
    }

    componentDidMount() {
        super.componentDidMount();
        this.props.displayProgressBar(true)
        this.loadInstruments().then(() =>
            this.loadValues().then(() =>
                this.props.displayProgressBar(false)
            )
        );
    }

    loadInstruments = () => {
        return fetch('/instruments/list')
            .then<Array<InstrumentDataRow>>(res => res.json())
            .then(instruments => this.setState({instruments}));
    }

    loadValues = () => {
        const params = new URLSearchParams();
        // params.append('ticker', 'CEZ.PR');
        return fetch(`/values/list?${params.toString()}`)
            .then<ValuesResponse>(res => res.json())
            .then(values => this.setState({values}));
    }

    addValue = (newValue: NewDataRow) => {
        if (newValue.ticker && newValue.date && newValue.value) {
            this.props.displayProgressBar(true);
            fetch('/values/new', {method: 'POST', body: JSON.stringify(newValue)})
                .then(res => {
                    this.loadValues().then(() => {
                        this.props.displayProgressBar(false);
                    });
                });
        }
    }

    render() {

        return <Box>
            <TableContainer>
                <Table size="small">
                    <TableHead>
                        <NewValueTableRow instruments={this.state.instruments} addValue={this.addValue} />
                    </TableHead>
                    <TableBody>
                        {this.state.values.map(
                            (item, i) => <TableRow key={i}>
                                <TableCell>{item.date}</TableCell>
                                <TableCell>{item.ticker}</TableCell>
                                <TableCell colSpan={2}>{this.formatCurrency(item.value, {currency: item.currency})}</TableCell>
                            </TableRow>
                        )}
                    </TableBody>
                </Table>
            </TableContainer>
        </Box>
    }
}